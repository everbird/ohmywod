#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import importlib
from itertools import chain
from os.path import join, dirname, abspath, isfile
from string import Template

import click


src = dirname(abspath(__file__))

ENV_GENERATE_FILES = {
        'devel': {
            'configs/templates/local_config.py.template': 'configs/local_config.py',
            'configs/templates/supervisord.conf.template': 'supervisord.conf',
            'configs/templates/ohmywod_local_config.py.template': 'ohmywod/local_config.py',
            'configs/templates/redis-store.conf.template': 'redis-store.conf',
            'configs/templates/redis-cache.conf.template': 'redis-cache.conf',
            },
        'product': {
            'configs/templates/supervisord.conf.template': 'supervisord.conf',
            'configs/templates/redis-store.conf.template': 'redis-store.conf',
            'configs/templates/redis-cache.conf.template': 'redis-cache.conf',
            }
        }

def _generate(env, config):
    for source, target in ENV_GENERATE_FILES[env].items():

        # Reload the generated local_config module
        importlib.reload(config)

        # Generate by generate_stacks
        with open(join(src, source)) as f:
            content = Template(f.read())\
                    .substitute(**config.__dict__)
            with open(join(src, target), 'w') as o:
                o.write(content)
                print(target, 'generated.')

@click.group()
def cli():
    pass


@cli.command()
def devel():
    from configs import config
    _generate('devel', config)
    print('Development config files done.')


@cli.command()
def product():
    from configs import config
    _generate('product', config)
    print('Production config files done.')


@cli.command()
def clean():
    fnames = chain.from_iterable(i.values() for i in ENV_GENERATE_FILES.values())
    for fname in fnames:
        fpath = join(src, fname)

        if isfile(fpath):
            os.remove(fpath)
            print(fname, 'removed.')
        else:
            print(fname, 'not exist.')


if __name__ == '__main__':
    cli()
