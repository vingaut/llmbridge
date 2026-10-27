#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Point d'entrée historique — identique à `python app.py`.

Conservé pour ceux qui ont découvert l'outil avec la version « serve.py + HTML
séparé » : le comportement est exactement le même.
"""
import sys

from app import main

if __name__ == "__main__":
    sys.exit(main())
