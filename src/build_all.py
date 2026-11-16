"""One-command reproducible data, model and anomaly build."""
from src.build_data import ROOT, build
from src.train_models import main as train
from src.anomalies import build as anomalies

if __name__ == '__main__':
    build(ROOT/'data/raw',ROOT/'data/processed',ROOT/'reports')
    train()
    anomalies()
