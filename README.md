# Furious

[![Github Deploy](https://github.com/LorenEteval/Furious/actions/workflows/deploy-pypi.yml/badge.svg?branch=main)](https://github.com/LorenEteval/Furious/actions/workflows/deploy-pypi.yml)
[![winget](https://img.shields.io/badge/winget-Available-brightgreen?logo=windows)](https://winstall.app/apps/LorenEteval.Furious)
[![release](https://img.shields.io/github/v/release/LorenEteval/Furious)](https://github.com/LorenEteval/Furious/releases)
[![license](https://img.shields.io/github/license/LorenEteval/Furious)](https://github.com/LorenEteval/Furious/blob/main/LICENSE)

A cross‑platform GUI proxy client based on PySide6. Support Xray-core & hysteria.

---

## Features

* 🖥️ **Cross‑platform** — Runs on **Windows**, **macOS** and **Linux**
* ⚙️ **Built‑in Support For Xray-core & Hysteria** — Shipped as Python bindings for convenience
* 🔗 **Protocol Support** — VLESS, VMess, Shadowsocks, Trojan, hysteria1 & hysteria2
* 🌐 **TUN Mode Support** — Available on Windows, macOS and Linux
* 📝 **Integrated configuration editor** — Fully editable configuration UI
* 🔄 **Subscription management** — Add, update or schedule refreshes
* 🔌 **Client UX** — One‑click Connect / Disconnect
* 📥 **Import** via share link, JSON, or QR Code
* 📤 **Export** as share link, JSON, or QR Code
* 🔓 **Open-source & Reproducible Builds**
* ...

## Install

You can install from the **[GitHub Releases](https://github.com/LorenEteval/Furious/releases)** page or directly from **PyPI**.

### 🪟 winget (Windows only)

```
winget install --id=LorenEteval.Furious -e
```

### 🐍 PyPI

```
pip install Furious-GUI
```

## Wiki

* 🌐 [TUN Mode](https://github.com/LorenEteval/Furious/wiki/TUN-Mode)
* 🔄 [Subscription Management](https://github.com/LorenEteval/Furious/wiki/Subscription-Management)
* 📦 [Install From PyPI](https://github.com/LorenEteval/Furious/wiki/Install-From-PyPI)

### Windows TUN (`wintun.dll`)

The Windows release is **amd64 (x64)** only. The [official Wintun](https://www.wintun.net/) package ships **one `wintun.dll` per CPU architecture** under `wintun\bin\` (for example `amd64`, `arm`, `arm64`, and `x86`).

You must use the DLL from **`wintun\bin\amd64\wintun.dll`**. Loading a DLL from another architecture (for example `arm64` or `x86`) can **crash TUN mode**.

Full setup (including where to place the file and administrator steps) is documented in **[TUN Mode](https://github.com/LorenEteval/Furious/wiki/TUN-Mode)**.

## Contributing

[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/LorenEteval/Furious)

## Credits

* [Xray-core](https://github.com/XTLS/Xray-core)
* [hysteria](https://github.com/apernet/hysteria)
* [tun2socks](https://github.com/xjasonlyu/tun2socks)

Special thanks to [@rakleed](https://github.com/rakleed) for adding the Windows package to winget.

---

## Donations

If you find this project useful, donations are warmly appreciated. They help sustain development, testing and future
improvements.

* BTC: `12Yp5Ffr6sXR5Ha5h43FnGW4RSCQeeJeUG`
* TRC20/TRON (USDT, TRON, ...): `TVHKXJq6S5cWzLwa7tLf6LoYB3T9ftiFkN`

## Star History

<a href="https://www.star-history.com/#LorenEteval/Furious&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=LorenEteval/Furious&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=LorenEteval/Furious&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=LorenEteval/Furious&type=date&legend=top-left" />
 </picture>
</a>

## License

Licensed under **[GPL v3.0](https://github.com/LorenEteval/Furious/blob/main/LICENSE)**.
