
Crypto Prediction Project — LSTM Model
=======================================
Prédit le prix futur (régression) sur une fenêtre glissante.

Pipeline :
  1. Chargement des CSV produits par data_collector.py
  2. Normalisation (MinMaxScaler)
  3. Création des séquences (sliding window)
  4. Entraînement LSTM (PyTorch)
  5. Évaluation (RMSE, MAE, MAPE)
  6. Sauvegarde du modèle + scaler

