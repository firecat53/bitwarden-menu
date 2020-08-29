#!/usr/bin/env python3  # pylint: disable=missing-docstring

from setuptools import setup

setup(name="bitwarden-menu",
      version="0.1.0",
      description="Dmenu/Rofi frontend for Bitwarden CLI tool",
      long_description=open('README.rst', 'rb').read().decode('utf-8'),
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/bitwarden-menu",
      download_url="https://github.com/firecat53/bitwarden-menu/tarball/0.1.0",
      scripts=['bwm'],
      data_files=[('share/doc/bwm', ['README.rst', 'LICENSE',
                                          'config.ini.example']),
                  ('share/man/man1', ['bwm.1'])],
      install_requires=["PyUserInput"],
      license="GPL3",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Topic :: Utilities',
      ],
      keywords=("dmenu rofi bitwarden bitwarden-menu bwm"),
     )
