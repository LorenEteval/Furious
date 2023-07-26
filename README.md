# Furious

A PySide6-based cross platform GUI client that launches your beloved GFW to outer space.
Support [Xray-core](https://github.com/XTLS/Xray-core)
and [hysteria](https://github.com/apernet/hysteria).

![Furious](https://raw.githubusercontent.com/LorenEteval/Furious/main/Icons/png/rocket-takeoff-window-400x400.png)

## Features

* Runs seamlessly on Windows, macOS and Linux.
* Built-in support for [Xray-core](https://github.com/XTLS/Xray-core)
  and [hysteria](https://github.com/apernet/hysteria). Cores are actually Python bindings that shipped with the source
  code. See more information: [Xray-core-python](https://github.com/LorenEteval/Xray-core-python)
  and [hysteria-python](https://github.com/LorenEteval/hysteria-python).
* Support import from JSON or share link(`vmess://...` or `vless://...`, including the newest REALITY share standard).
* Support export to JSON, share link or QRCode.
* Two built-in routing mode support: Bypass Mainland China(with Ads filter) and Global. You can also choose to use your
  own routing rules.
* Built-in editor support.
* Ability to store and handle hundreds of servers, or even more.
* VPN-client user experience.
* Support system theme detection and switch to dark/light theme automatically.
* Multiple language support: English, Spanish, Simplified Chinese and Traditional Chinese.
* Built-in user-friendly feature.
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

```
pip install -r requirements.txt
```

Run:

```
python -m Furious
```

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

License under [GPL v3.0](https://github.com/LorenEteval/Furious/blob/main/LICENSE)
