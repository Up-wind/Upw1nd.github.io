---
title: 如何使用 nc/ncat
date: 2022-04-22
categories:
- Tools
tags: [CTF]
description: 本文用于介绍 CTF 比赛中不少题目需要使用的 nc/ncat 工具。
---

## `nc` 是什么？

`nc/ncat` 是 netcat 的缩写，它用来在两台机器之间建立 `TCP/UDP` 连接，并通过标准的输入输出进行数据的读写。

一般来说，有很多 CTF 题目都会要求你使用 `nc` 连接到特定的服务器，并且进行交互，获得 flag。

## 如何安装 `nc` ？

### Linux & MacOS

`nc` 命令在 MacOS 中是自带的，在 Linux 中一般自带，或是可以使用相应的软件包管理器安装（例如，在 Debian/Ubuntu 中这个包名叫 netcat）。

当然，如果你在看这篇文章，你的操作系统很有可能是 Windows。它不自带 `nc`，尽管可以用 WSL 或者虚拟机的方式解决，但是如果你觉得这样太麻烦了，也有另外一些方法。

### Windows

我们在这里提供了一份编译完成的 `ncat` 程序。下载下来即可。

[ncat.zip 下载](http://210.30.97.133:8008/tools/ncat.zip)

> `ncat` 是由 Nmap 项目开发的“重置版的 Netcat”，和 `nc` 实际上是两个不同的程序。Debian 和 Ubuntu 下的 `nc` 程序版本亦有不同，但在我们接下来的使用上基本没有区别。

## 如何使用 `nc`?

### Windows

直接双击，你会看到一个黑色窗口一扫而过——这是正常现象。你需要使用「命令提示符」或者「PowerShell」来访问这个程序。

在资源管理器的地址栏中输入 `cmd` 或者 `powershell` ，进入对应的程序中。

![image-20220422234254085](https://up-wind.github.io/assets/2022-04-22-how-to-use-nc/image-20220422234254085.png)

- 如果你使用的是 PowerShell（蓝色背景），输入 `.\ncat`（根据 `nc` 对应的名称不同而不同）。
- 如果你使用的是命令提示符（黑色背景），输入 `ncat`（根据 `nc` 对应的名称不同而不同）。

```
Ncat: You must specify a host to connect to. QUITTING.
```

出现类似上面的输出，说明运行成功了。

### Linux & macOS

打开「终端」，输入 `nc`。

```
$ nc
usage: nc [-46AacCDdEFhklMnOortUuvz] [-K tc] [-b boundif] [-i interval] [-p source_port] [--apple-delegate-pid pid] [--apple-delegate-uuid uuid]
	  [-s source_ip_address] [-w timeout] [-X proxy_version]
	  [-x proxy_address[:port]] [hostname] [port[s]]
```

出现类似上面的输出，说明运行成功了。

接下来，请使用 `nc [hostname] [port]` 来访问我们的题目。

### 示例

在我们使用浏览器上网的时候，我们和服务器使用了 HTTP 协议进行连接。一般来说，默认是 80 端口。

我们可以使用 `nc` 尝试一次与网页服务器的连接，以百度为例。

输入 `nc www.baidu.com 80`（或者 `ncat www.baidu.com 80`，或者 `.\ncat www.baidu.com 80`，请根据以上的介绍自行修改），程序会等待你的输入。

输入 `GET / HTTP/1.0`。这表示，我们使用 `HTTP/1.0` 这个协议版本，用 `GET` 的方式请求根 `/`。输入两下回车，代表我们的 HTTP 请求完成。如果你的网络畅通，百度的网页服务器会立刻返回大量信息，可以自行搜索，了解它们的含义。现在，你成功在不使用浏览器的情况下完成了一次与百度网站的连接！

![image-20220422234859024](https://up-wind.github.io/assets/2022-04-22-how-to-use-nc/image-20220422234859024.png)

如果你成功了，那么你可以开始愉快地完成我们的题目了！

> 参考：[萌新入门手册：如何使用 nc/ncat? - LUG @ USTC](https://lug.ustc.edu.cn/planet/2019/09/how-to-use-nc/)



