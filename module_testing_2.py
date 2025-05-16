import pytest
import pandas as pd
from module_testing import load_data, preprocess_data, train_arima_model, forecast

# Sample dummy data for testing
@pytest.fixture
def dummy_data():
    dates = pd.date_range(start='2024-11-12', periods=10000, freq = '10min')
    temps = pd.Series(range(10000), index=dates)
    precp = pd.Series(range(10000), index=dates)
    humid = pd.Series(range(10000), index=dates)
    leaf_wet = pd.Series(range(10000), index=dates)
    df = pd.DataFrame({'temperature': temps,'rainfall':precp,'leaf_wetness':leaf_wet,'humidity':humid})
    df = df.reset_index().rename(columns={'index': 'timestamp'})
    return df



def test_arima_model_training(dummy_data):
    processed = preprocess_data(dummy_data)
    model_fit = train_arima_model(processed, order=(1,1,1),seasonality_order=(1,1,1,24))
    assert hasattr(model_fit, 'forecast'), "Model training failed or object not correct."

def test_forecast_output_length(dummy_data):
    processed = preprocess_data(dummy_data)
    model_fit = train_arima_model(processed, order=(1,1,1),seasonality_order=(1,1,1,24))
    preds = forecast(model_fit, steps=10)
    assert len(preds) == 10, "Forecast length mismatch"

def test_forecast_returns_series(dummy_data):
    processed = preprocess_data(dummy_data)
    model_fit = train_arima_model(processed, order=(1,1,1),seasonality_order=(1,1,1,24))
    preds = forecast(model_fit)
    assert isinstance(preds, pd.Series), "Forecast output is not a pandas Series" 