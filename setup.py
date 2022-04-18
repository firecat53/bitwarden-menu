#!/usr/bin/env python3  # pylint: disable=missing-docstring

from setuptools import setup

setup(name="bitwarden-menu",
      version="v0.4.0",
      description="Dmenu/Rofi frontend for Bitwarden CLI tool",
      long_description=open('README.md', 'rb').read().decode('utf-8'),
      long_description_content_type="text/markdown",
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/bitwarden-menu",
      download_url="https://github.com/firecat53/bitwarden-menu/tarball/v0.4.0",
      packages=['bwm'],
      entry_points={
          'console_scripts': ['bwm=bwm.__main__:main']
      },
      data_files=[('share/doc/bitwarden-menu', ['README.md', 'LICENSE',
                                                'config.ini.example']),
                  ('share/doc/bitwarden-menu/docs', ['docs/install.md',
                                                     'docs/configure.md',
                                                     'docs/usage.md']),
                  ('share/man/man1', ['bwm.1'])],
      install_requires=["pynput", "xdg"],
      license="MIT",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: End Users/Desktop',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 3.7',
          'Programming Language :: Python :: 3.8',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Topic :: Utilities',
      ],
      keywords=("dmenu rofi bitwarden bitwarden-menu bwm"),
      )
