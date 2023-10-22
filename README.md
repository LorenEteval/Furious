# Furious

[![Build Furious](https://github.com/LorenEteval/Furious/actions/workflows/wheels.yml/badge.svg?branch=main)](https://github.com/LorenEteval/Furious/actions/workflows/wheels.yml)

[简体中文](https://github.com/LorenEteval/Furious#%E5%8A%9F%E8%83%BD)

A PySide6-based cross platform GUI client that launches your beloved GFW to outer space.
Support [Xray-core](https://github.com/XTLS/Xray-core)
and [hysteria](https://github.com/apernet/hysteria).

![Furious](https://raw.githubusercontent.com/LorenEteval/Furious/main/Icons/png/rocket-takeoff-window-400x400.png)

## Features

* Runs on Windows, macOS and Linux.
* Built-in support for [Xray-core](https://github.com/XTLS/Xray-core)
  and [hysteria](https://github.com/apernet/hysteria)(compatible with hy1 and hy2). Cores are actually Python bindings
  that shipped with the source code. See more
  information: [Xray-core-python](https://github.com/LorenEteval/Xray-core-python), [hysteria-python](https://github.com/LorenEteval/hysteria-python)
  and [hysteria2-python](https://github.com/LorenEteval/hysteria2-python).
* Support TUN mode on Windows and macOS. (experimental, requires administrator/root privilege)
* Support subscription.
* Support import from JSON.
* Support import from share link:
    * VMess
    * VLESS, including [REALITY](https://github.com/XTLS/REALITY)
    * Shadowsocks
    * Trojan
* Support export to JSON, share link or QRCode.
* Built-in routing mode support: `Bypass Mainland China(with Ads filter)`, `Bypass Iran(with Ads filter)`,
  [`Route My Traffic Through Tor`](https://github.com/LorenEteval/Furious/wiki/Route-My-Traffic-Through-Tor)
  and `Global`. You can also choose to customize your own routing rules.
* Built-in editor support.
* VPN-client user experience.
* Support system theme detection and switch to dark/light theme automatically.
* Multiple language support: English, Spanish, Simplified Chinese and Traditional Chinese.
* Built-in user-friendly feature such as startup on boot.
* ...

## Install

There are **two** ways of installing Furious:

1. Download pre-built binary release. In this case there is no dependency required:
    * For Windows users: Download zip file in the [release](https://github.com/LorenEteval/Furious/releases) page that
      contains pre-built binaries.
    * For macOS users: Download dmg file in the [release](https://github.com/LorenEteval/Furious/releases) page. Support
      Apple Silicon(arm64) and Intel Chip(x86_64).
2. Install via `pip` (requires **Python 3.8 and above**). You need to follow instructions below. (available for **all**
   platform)

### Core Building Tools

> Note: These steps are the same in [Xray-core-python](https://github.com/LorenEteval/Xray-core-python)
> or [hysteria-python](https://github.com/LorenEteval/hysteria-python) *Core Building Tools* steps.

> Note: hysteria requires go 1.21+ to build since v2.0.3

As mentioned above, cores are shipped as Python bindings to support cross-platform running. So to install Furious
via `pip` you must have tools ready for building these bindings for your current platform first. Core building requires:

* [go](https://go.dev/doc/install) `1.20.x` in your PATH. To check go is ready,
  type `go version`. Also, if google service is blocked in your region(such as Mainland China), you have to configure
  your GOPROXY to be able to pull go packages. For Chinese users, refer to [goproxy.cn](https://goproxy.cn/) for more
  information.
* [cmake](https://cmake.org/download/) in your PATH. To check cmake is ready, type `cmake --version`.
* A working GNU C++ compiler(i.e. GNU C++ toolchains). To check GNU C++ compiler is ready, type `g++ --version`. These
  tools should have been installed in Linux or macOS by default. If you don't have GNU C++ toolchains(especially for
  Windows users) anyway:

    * For Linux users: type `sudo apt update && sudo apt install g++` and that should work out fine.
    * For Windows users: install [MinGW-w64](https://sourceforge.net/projects/mingw-w64/files/mingw-w64/)
      or [Cygwin](https://www.cygwin.com/) and make sure you have add them to PATH.

These tools should be installed easily using `brew install` on macOS, or using `sudo apt install` on Linux.

### Install Furious

> Note: Install Furious in a Python virtual environment(i.e. venv) is recommended.

> Note: Furious supports **minimum PySide6 version 6.1.0** since **version 0.2.11**.

> Note: `PySide6-Essentials` is available [since Qt 6.3.0](https://pypi.org/project/PySide6-Essentials/#history).
> If `PySide6-Essentials` is not found via `pip` on your platform then it means you have to install `PySide6` package
> (i.e. Qt version < 6.3.0):
>
> ```
> pip install PySide6
> ```

```
pip install Furious-GUI
```

To launch Furious, type:

```
Furious
```

## Run From Source

Clone this repository and enter the project folder. Install requirements:

> Note: Install requirements in a Python virtual environment(i.e. venv) is recommended.

> Note: To install requirements successfully you will also need
> those [Core Building Tools](https://github.com/LorenEteval/Furious#core-building-tools) above.

```
pip install -r requirements.txt
```

Run:

```
python -m Furious
```

> Note: Furious will ignore current startup on boot request if it's lauched from source.

## Wiki

* [Route My Traffic Through Tor](https://github.com/LorenEteval/Furious/wiki/Route-My-Traffic-Through-Tor)
* [TUN Mode](https://github.com/LorenEteval/Furious/wiki/TUN-Mode)

## Build Status

See the build result in [github actions](https://github.com/LorenEteval/Furious/actions).

| Platform     | Python 3.8-Python 3.11 |
|--------------|:----------------------:|
| ubuntu 20.04 |   :heavy_check_mark:   |
| ubuntu 22.04 |   :heavy_check_mark:   |
| windows-2019 |   :heavy_check_mark:   |
| windows-2022 |   :heavy_check_mark:   |
| macos-11     |   :heavy_check_mark:   |
| macos-12     |   :heavy_check_mark:   |
| macos-13     |   :heavy_check_mark:   |

## Core Installation Script

Below are some one-click/automatic installation script that's been tested to work in Furious.

(`XXX Support` is referring to Furious)

| Project Address                                                   |  Supported Core Installation  | Share Link Import Support? | JSON Import Support? |
|-------------------------------------------------------------------|:-----------------------------:|:--------------------------:|:--------------------:|
| [233boy/v2ray](https://github.com/233boy/v2ray)                   |          v2ray-core           |            Yes             |          /           |
| [mack-a/v2ray-agent](https://github.com/mack-a/v2ray-agent)       | v2ray-core/Xray-core/hysteria |            Yes             |         Yes          |
| [zxcvos/Xray-script](https://github.com/zxcvos/Xray-script)       |           Xray-core           |            Yes             |          /           |
| [aleskxyz/reality-ezpz](https://github.com/aleskxyz/reality-ezpz) |      Xray-core/hysteria       |            Yes             |         Yes          |
| [emptysuns/Hi_Hysteria](https://github.com/emptysuns/Hi_Hysteria) |           hysteria            |             No             |         Yes          |

## License

License under [GPL v3.0](https://github.com/LorenEteval/Furious/blob/main/LICENSE).

---

## 功能

* 在Windows、macOS和Linux上运行。
* 内置对[Xray-core](https://github.com/XTLS/Xray-core)和[hysteria](https://github.com/apernet/hysteria)
  的支持（对于hysteria，兼容hy1和hy2）。Core实际是与源代码一起发行的Python绑定。更多信息: [Xray-core-python](https://github.com/LorenEteval/Xray-core-python),
  [hysteria-python](https://github.com/LorenEteval/hysteria-python)
  和[hysteria2-python](https://github.com/LorenEteval/hysteria2-python)。
* 在Windows和macOS上支持TUN模式。（实验性功能，需要管理员/root权限）
* 支持订阅。
* 支持从JSON导入。
* 支持从分享链接导入：
    * VMess
    * VLESS，包括[REALITY](https://github.com/XTLS/REALITY)
    * Shadowsocks
    * Trojan
* 支持导出为JSON、分享链接或二维码。
* 内置路由模式支持：`绕过中国大陆（带广告过滤）`、`绕过伊朗（带广告过滤）`、
  [`通过Tor路由我的流量`](https://github.com/LorenEteval/Furious/wiki/Route-My-Traffic-Through-Tor)
  和`全球`。也可选择使用自己的路由规则。
* 内置编辑器支持。
* VPN客户端的使用体验。
* 支持系统主题检测并自动切换深色/浅色主题。
* 多语言支持：英语、西班牙语、简体中文和繁体中文。
* 内置用户友好的功能，例如开机自启动等。
* ...

## 安装

有**两种**安装Furious的方式：

1. 下载打包好的二进制版本，无需其它依赖：
    * Windows用户：在[release](https://github.com/LorenEteval/Furious/releases)界面下载打包好的zip文件。
    * macOS用户：在[release](https://github.com/LorenEteval/Furious/releases)界面下载dmg文件。支持苹果芯片（arm64）和Intel芯片（x86_64）
2. 通过`pip`安装（需要**Python 3.8及以上**），且需要按照以下步骤进行操作。（适用于**所有**平台）

### Core编译工具

> 注意: 这些步骤与[Xray-core-python](https://github.com/LorenEteval/Xray-core-python)
> 和[hysteria-python](https://github.com/LorenEteval/hysteria-python)中*Core Building Tools*一节的步骤一样。

> 注意: hysteria从v2.0.3开始需要go 1.21+编译

根据上文所述，Core是对应的Python绑定以支持跨平台运行。所以通过`pip`安装Furious首先得准备好当前平台的Core编译工具。编译Core需要：

* [go](https://go.dev/doc/install) `1.20.x` 在PATH中。要检查go是否就绪，输入`go version`
  。另外，如果当前所在地区（例如中国大陆）屏蔽了google服务，还需要配置GOPROXY才能拉取go包。对于中国用户，请访问[goproxy.cn](https://goproxy.cn/)
  了解更多信息。
* [cmake](https://cmake.org/download/)在PATH中. 要检查cmake是否就绪，输入`cmake --version`。
* GNU C++编译器（即GNU C++工具链）。要检查GNU C++编译器是否准备就绪，输入`g++ --version`
  。默认情况下，这些工具应该已安装在Linux或macOS中。如果仍然没有GNU C++工具链（特别是对于Windows用户）：

    * 对于Linux用户：输入`sudo apt update && sudo apt install g++`。
    * 对于Windows用户：安装[MinGW-w64](https://sourceforge.net/projects/mingw-w64/files/mingw-w64/)
      或[Cygwin](https://www.cygwin.com/)并确保已将它们添加至PATH。

这些工具可用`brew install`在macOS上安装，或者用`sudo apt install`在Linux上安装。

### 安装Furious

> 注意：推荐在Python虚拟环境(i.e. venv)中安装。

> 注意：Furious从**0.2.11**起支持**最低PySide6版本6.1.0**。

> 注意：`PySide6-Essentials`[从 Qt 6.3.0](https://pypi.org/project/PySide6-Essentials/#history)可用。
> 如果`pip`找不到`PySide6-Essentials`，那么你应该安装`PySide6`（即Qt小于6.3.0的版本）:
>
> ```
> pip install PySide6
> ```

```
pip install Furious-GUI
```

启动Furious，输入：

```
Furious
```

## 从源码运行

克隆该仓库并进入项目文件夹。安装所需依赖包：

> 注意：推荐在Python虚拟环境(i.e. venv)中安装依赖。

> 注意：为了安装依赖包成功，仍然需要准备好上文中的Core编译工具。

```
pip install -r requirements.txt
```

运行:

```
python -m Furious
```

> 注意：如果从源码运行，Furious将忽略当前的开机自启动请求。

## License

License under [GPL v3.0](https://github.com/LorenEteval/Furious/blob/main/LICENSE).
