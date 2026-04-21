"""ML model training utilities for signal scoring.

Trains LightGBM and XGBoost models on historical trading data to predict
signal confidence. Models learn which features lead to profitable signals.

Training pipeline:
1. Generate features from historical OHLCV + signals
2. Label with trade outcomes (profitable = 1, loss = 0)
3. Train/test split
4. Model training with hyperparameter tuning
5. Model serialization and performance reporting
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False
    log.warning("LightGBM not installed. Install with: pip install lightgbm")

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False
    log.warning("XGBoost not installed. Install with: pip install xgboost")


class SignalDataset:
    """Manages training data for ML signal scoring."""
    
    def __init__(self) -> None:
        self.features_list: list[dict] = []
        self.labels: list[int] = []
        self.signal_metadata: list[dict] = []
    
    def add_training_example(
        self,
        features: dict,
        label: int,
        metadata: Optional[dict] = None,
    ) -> None:
        """Add a training example.
        
        Args:
            features: Feature dict (will be converted to array)
            label: 1 for profitable signal, 0 for losing signal
            metadata: Optional metadata for analysis
        """
        self.features_list.append(features)
        self.labels.append(label)
        self.signal_metadata.append(metadata or {})
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame for training."""
        return pd.DataFrame(self.features_list)
    
    def get_xy_arrays(self) -> Tuple[np.ndarray, np.ndarray]:
        """Get feature matrix and labels."""
        df = self.to_dataframe()
        X = df.values.astype(np.float32)
        y = np.array(self.labels, dtype=np.int32)
        return X, y


class LightGBMTrainer:
    """Train LightGBM model for signal scoring."""
    
    def __init__(self, model_params: Optional[dict] = None) -> None:
        if not HAS_LIGHTGBM:
            raise RuntimeError("LightGBM not installed")
        
        self.model_params = model_params or self._default_params()
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
    
    @staticmethod
    def _default_params() -> dict:
        """Default LightGBM hyperparameters tuned for signal scoring."""
        return {
            "objective": "binary",
            "metric": "auc",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
        }
    
    def train(
        self,
        dataset: SignalDataset,
        test_size: float = 0.2,
        num_rounds: int = 100,
    ) -> dict:
        """Train LightGBM model.
        
        Returns:
            Performance metrics dict
        """
        X, y = dataset.get_xy_arrays()
        self.feature_names = dataset.to_dataframe().columns.tolist()
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=test_size, random_state=42
        )
        
        # Convert to LightGBM dataset
        train_data = lgb.Dataset(X_train, label=y_train, feature_names=self.feature_names)
        
        # Train
        self.model = lgb.train(
            self.model_params,
            train_data,
            num_boost_round=num_rounds,
            valid_sets=[lgb.Dataset(X_test, label=y_test)],
            valid_names=["test"],
            callbacks=[lgb.early_stopping(5), lgb.log_evaluation(-1)],
        )
        
        # Evaluate
        y_pred = self.model.predict(X_test)
        from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
        
        metrics = {
            "auc": roc_auc_score(y_test, y_pred),
            "precision": precision_score(y_test, (y_pred > 0.5).astype(int), zero_division=0),
            "recall": recall_score(y_test, (y_pred > 0.5).astype(int), zero_division=0),
            "f1": f1_score(y_test, (y_pred > 0.5).astype(int), zero_division=0),
        }
        
        log.info(f"LightGBM training complete. Metrics: {metrics}")
        return metrics
    
    def save(self, path: Path) -> None:
        """Serialize model and scaler."""
        import pickle
        
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)
        
        log.info(f"LightGBM model saved to {path}")
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance from model."""
        if self.model is None:
            return {}
        
        importance = self.model.feature_importance()
        return dict(zip(self.feature_names, importance))


class XGBoostTrainer:
    """Train XGBoost model for signal scoring."""
    
    def __init__(self, model_params: Optional[dict] = None) -> None:
        if not HAS_XGBOOST:
            raise RuntimeError("XGBoost not installed")
        
        self.model_params = model_params or self._default_params()
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = []
    
    @staticmethod
    def _default_params() -> dict:
        """Default XGBoost hyperparameters."""
        return {
            "objective": "binary:logistic",
            "eval_metric": "auc",
            "max_depth": 6,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "random_state": 42,
        }
    
    def train(
        self,
        dataset: SignalDataset,
        test_size: float = 0.2,
        num_rounds: int = 100,
    ) -> dict:
        """Train XGBoost model."""
        X, y = dataset.get_xy_arrays()
        self.feature_names = dataset.to_dataframe().columns.tolist()
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=test_size, random_state=42
        )
        
        # Convert to DMatrix
        dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=self.feature_names)
        dtest = xgb.DMatrix(X_test, label=y_test, feature_names=self.feature_names)
        
        # Train
        evals = [(dtrain, "train"), (dtest, "eval")]
        self.model = xgb.train(
            self.model_params,
            dtrain,
            num_boost_round=num_rounds,
            evals=evals,
            early_stopping_rounds=5,
            verbose_eval=False,
        )
        
        # Evaluate
        y_pred = self.model.predict(dtest)
        from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
        
        metrics = {
            "auc": roc_auc_score(y_test, y_pred),
            "precision": precision_score(y_test, (y_pred > 0.5).astype(int), zero_division=0),
            "recall": recall_score(y_test, (y_pred > 0.5).astype(int), zero_division=0),
            "f1": f1_score(y_test, (y_pred > 0.5).astype(int), zero_division=0),
        }
        
        log.info(f"XGBoost training complete. Metrics: {metrics}")
        return metrics
    
    def save(self, path: Path) -> None:
        """Serialize model and scaler."""
        import pickle
        
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "scaler": self.scaler}, f)
        
        log.info(f"XGBoost model saved to {path}")
    
    def get_feature_importance(self) -> dict[str, float]:
        """Get feature importance."""
        if self.model is None:
            return {}
        
        importance = self.model.get_score(importance_type="weight")
        return {k.replace("f", ""): v for k, v in importance.items()}


class ModelEvaluator:
    """Evaluate and compare trained models."""
    
    @staticmethod
    def compare_models(
        dataset: SignalDataset,
        use_lightgbm: bool = True,
        use_xgboost: bool = True,
    ) -> dict[str, dict]:
        """Train and compare both models."""
        results = {}
        
        if use_lightgbm and HAS_LIGHTGBM:
            try:
                lgb_trainer = LightGBMTrainer()
                lgb_metrics = lgb_trainer.train(dataset)
                results["lightgbm"] = {
                    "metrics": lgb_metrics,
                    "importance": lgb_trainer.get_feature_importance(),
                }
            except Exception as e:
                log.exception(f"LightGBM training failed: {e}")
        
        if use_xgboost and HAS_XGBOOST:
            try:
                xgb_trainer = XGBoostTrainer()
                xgb_metrics = xgb_trainer.train(dataset)
                results["xgboost"] = {
                    "metrics": xgb_metrics,
                    "importance": xgb_trainer.get_feature_importance(),
                }
            except Exception as e:
                log.exception(f"XGBoost training failed: {e}")
        
        return results
