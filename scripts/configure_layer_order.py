#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vela import layer_order
parser = argparse.ArgumentParser(description='Order MangoHud before lsfg-vk; requires restarting the game.')
parser.add_argument('--remove', action='store_true')
args = parser.parse_args()
if args.remove:
    layer_order.remove()
    print('Removed Vela layer ordering.')
else:
    print('Configured MangoHud → lsfg-vk:', layer_order.configure())
    print('The new order takes effect the next time the game starts.')
