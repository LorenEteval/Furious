# Copyright (C) 2023  Loren Eteval <loren.eteval@proton.me>
#
# This file is part of Furious.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from Furious.Version import __version__

from setuptools import setup, find_packages

with open('README.md', 'r', encoding='utf-8') as file:
    long_description = file.read()

setup(
    name='Furious-GUI',
    version=__version__,
    license='GPL v3.0',
    description='A PySide6-based cross platform GUI client that launches your beloved GFW to outer space.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='Loren Eteval',
    author_email='loren.eteval@proton.me',
    url='https://github.com/LorenEteval/Furious',
    packages=find_packages(),
    package_data={'Furious': ['Data/**']},
    include_package_data=True,
    install_requires=[
        'PySide6-Essentials',
        'Xray-core',
        'hysteria',
        'hysteria2 > 2.0.0',
        'tun2socks > 2.5.1',
        'ujson',
        'pybase64',
        'pyqrcode',
        'pypng',
        'ping3',
        'sysproxy; sys_platform == "win32"',
        'darkdetect; sys_platform != "darwin"',
        'darkdetect[macos-listener]; sys_platform == "darwin"',
    ],
    entry_points={
        'gui_scripts': [
            'Furious = Furious.__main__:main',
        ],
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Intended Audience :: End Users/Desktop',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Operating System :: OS Independent',
        'Topic :: Internet',
        'Topic :: Internet :: Proxy Servers',
    ],
)
