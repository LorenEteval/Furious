# Furious

A PySide6-based cross platform GUI client that launches your beloved GFW to outer space.
Support [Xray-core](https://github.com/XTLS/Xray-core)
and [hysteria](https://github.com/apernet/hysteria).

![Furious](https://raw.githubusercontent.com/LorenEteval/Furious/main/Icons/png/rocket-takeoff-window-400x400.png)

## Features

* Runs seamlessly on Windows, macOS and Linux(see the screenshot below).
* Built-in support for [Xray-core](https://github.com/XTLS/Xray-core)
  and [hysteria](https://github.com/apernet/hysteria). Cores are actually Python bindings that shipped with the source
  code. See more information: [Xray-core-python](https://github.com/LorenEteval/Xray-core-python)
  and [hysteria-python](https://github.com/LorenEteval/hysteria-python).
* Support import from JSON or share link(`vmess://...`, `vless://...` or `ss://`, including the
  newest [REALITY](https://github.com/XTLS/REALITY) share standard).
* Support export to JSON, share link or QRCode.
* Two built-in routing mode support: Bypass Mainland China(with Ads filter) and Global. You can also choose to use your
  own routing rules.
* Built-in editor support.
* VPN-client user experience.
* Support system theme detection and switch to dark/light theme automatically.
* Multiple language support: English, Spanish, Simplified Chinese and Traditional Chinese.
* Built-in user-friendly feature such as startup on boot.
* ...

## Sreenshot

### Windows

![Windows-Light-EN](https://raw.githubusercontent.com/LorenEteval/Furious/main/Screenshot/Windows-Light-EN.png)

![Windows-Light-CN](https://raw.githubusercontent.com/LorenEteval/Furious/main/Screenshot/Windows-Light-CN.png)

### macOS

![macOS-Light](https://raw.githubusercontent.com/LorenEteval/Furious/main/Screenshot/macOS-Light.png)

![macOS-Dark](https://raw.githubusercontent.com/LorenEteval/Furious/main/Screenshot/macOS-Dark.png)

### Ubuntu

![Ubuntu-Light](https://raw.githubusercontent.com/LorenEteval/Furious/main/Screenshot/Ubuntu-Light.png)

![Ubuntu-Dark](https://raw.githubusercontent.com/LorenEteval/Furious/main/Screenshot/Ubuntu-Dark.png)

## Install

> Note: Due to better binary files compatibility on Windows platform, Windows users can skip this section and
> download zip file in the [release](https://github.com/LorenEteval/Furious/releases) page that contains
> pre-built binaries. Otherwise you need to follow the instructions below.

### Core Building Tools

> Note: These steps are the same in [Xray-core-python](https://github.com/LorenEteval/Xray-core-python)
> or [hysteria-python](https://github.com/LorenEteval/hysteria-python) *Core Building Tools* steps.

As mentioned above, cores are shipped as Python bindings to support cross-platform running. So to install Furious you
must have tools ready for building these bindings for your current platform first. Core building requires:

* [go](https://go.dev/doc/install) in your PATH. go 1.20.0 and above is recommended. To check go is ready,
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

### Install Furious

Furious requires **Python 3.8 and above**.

```
pip install Furious-GUI
```

If the installation is successful, you will have a executable script(or `.exe` on Windows) in your PATH(if it's not in
the PATH, you can always add the script location to the PATH later). That's Furious's application entry point.

Any time you want to launch Furious, type:

```
Furious
```

Furious will enable startup on boot by default if it's launched for the first time. Happy browsing!

## Run From Source

Clone this repository and enter the project folder. Install requirements:

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

## Core Installation Script

Below are some one-click/automatic installation script that's been tested to work in Furious.

| Project Address                                                   |  Supported Core Installation  | Share Link Import Support? | JSON Import Support? |
|-------------------------------------------------------------------|:-----------------------------:|:--------------------------:|:--------------------:|
| [233boy/v2ray](https://github.com/233boy/v2ray)                   |          v2ray-core           |            Yes             |          /           |
| [mack-a/v2ray-agent](https://github.com/mack-a/v2ray-agent)       | v2ray-core/Xray-core/hysteria |            Yes             |         Yes          |
| [zxcvos/Xray-script](https://github.com/zxcvos/Xray-script)       |           Xray-core           |            Yes             |          /           |
| [aleskxyz/reality-ezpz](https://github.com/aleskxyz/reality-ezpz) |           Xray-core           |            Yes             |          /           |
| [emptysuns/Hi_Hysteria](https://github.com/emptysuns/Hi_Hysteria) |           hysteria            |             No             |         Yes          |

## License

License under [GPL v3.0](https://github.com/LorenEteval/Furious/blob/main/LICENSE).

---

## 功能

* 可在Windows、macOS和Linux上运行（见上文运行截图）。
* 内置对[Xray-core](https://github.com/XTLS/Xray-core)和[hysteria](https://github.com/apernet/hysteria)的支持。
  Core实际是与源代码一起发行的Python绑定。更多信息: [Xray-core-python](https://github.com/LorenEteval/Xray-core-python), [hysteria-python](https://github.com/LorenEteval/hysteria-python)。
* 支持从JSON或分享链接导入（`vmess://...`，`vless://...`或`ss://`，包括最新的[REALITY](https://github.com/XTLS/REALITY)
  分享标准）。
* 支持导出为JSON、分享链接或二维码。
* 内置两种路由模式的支持：绕过中国大陆（带广告过滤）和全球。也可选择使用自己的路由规则。
* 内置编辑器支持。
* VPN客户端的使用体验。
* 支持系统主题检测并自动切换深色/浅色主题。
* 多语言支持：英语、西班牙语、简体中文和繁体中文。
* 内置用户友好的功能，例如开机自启动等。
* ...

## 安装

> 注意：由于Windows有更好的二进制文件兼容性，Windows用户可以跳过本节并在
[release](https://github.com/LorenEteval/Furious/releases)页面中下载打包好的zip文件。否则安装过程需要按照以下步骤进行。

### Core编译工具

> 注意: 这些步骤与[Xray-core-python](https://github.com/LorenEteval/Xray-core-python)
> 和[hysteria-python](https://github.com/LorenEteval/hysteria-python)中*Core Building Tools*一节的步骤一样。

根据上文所述，Core是对应的Python绑定以支持跨平台运行。所以要安装Furious你首先得准备好当前平台的Core编译工具。编译Core需要：

* [go](https://go.dev/doc/install)在PATH中。建议使用go 1.20.0及以上版本。要检查go是否就绪，输入`go version`
  。另外，如果你当前所在地区（例如中国大陆）屏蔽了google服务，还需要配置GOPROXY才能拉取go包。对于中国用户，请访问[goproxy.cn](https://goproxy.cn/)
  了解更多信息。
* [cmake](https://cmake.org/download/)在PATH中. 要检查cmake是否就绪，输入`cmake --version`。
* GNU C++编译器（即GNU C++工具链）。要检查GNU C++编译器是否准备就绪，输入`g++ --version`
  。默认情况下，这些工具应该已安装在Linux或macOS中。如果你仍然没有GNU C++工具链（特别是对于Windows用户）：

    * 对于Linux用户：输入`sudo apt update && sudo apt install g++`。
    * 对于Windows用户：安装[MinGW-w64](https://sourceforge.net/projects/mingw-w64/files/mingw-w64/)
      或[Cygwin](https://www.cygwin.com/)并确保已将它们添加至PATH。

### 安装Furious

运行Furious需要**Python 3.8及以上**版本。

```
pip install Furious-GUI
```

如果安装成功，PATH中将有一个可执行脚本（在Windows上是.exe）（如果它不在PATH中，可以稍后将脚本路径添加至PATH），这是Furious的应用程序入口点。

要启动Furious，输入：

```
Furious
```

如果是首次运行，Furious将默认启用开机启动。Happy browsing!

## 从源码运行

克隆该仓库并进入项目文件夹。安装所需依赖包：

> 注意：为了安装依赖包成功，你仍然需要准备好上文中的Core编译工具。

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
