#!/usr/bin/env python3
"""
Entry point ketika di-run dengan: python -m src.bot

File ini otomatis dipanggil oleh Python saat package di-execute sebagai modul.
Mendukung systemd service dan manual execution.
"""

if __name__ == "__main__":
    from .main import main
    main()
