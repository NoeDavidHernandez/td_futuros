#!/bin/bash
echo "Iniciando Passivbot en segundo plano..."
passivbot live configs/examples/default_trailing_grid_long_npos7.json -u binance_01 --skip-rust-compile &

echo "Iniciando el Dashboard en el puerto principal..."
gunicorn custom_dashboard:app --bind 0.0.0.0:$PORT
