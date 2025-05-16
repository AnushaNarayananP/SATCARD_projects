

import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
import numpy as np

def load_data(filepath):
    return pd.read_csv(filepath, parse_dates=['DATE'], index_col='DATE')

def preprocess_data(data):
    
    start_date = '2000-01-01'
    end_date = '2024-09-30'
    df_filtered = data[((data['timestamp'] >= start_date) & (data['timestamp'] <= end_date)) | (data['timestamp'] > "2025-03-12")]
    df = data[~data.index.isin(df_filtered.index)]
    df.set_index('timestamp', inplace=True)
    
    df['timestamp_hourly'] = df.index.floor('H')  # Round timestamps to nearest hour
    df_hourly = df.groupby('timestamp_hourly').mean().reset_index()
    # Set timestamp as index
    df['timestamp_hourly'] = df.index.floor('H')
    df_hourly.set_index('timestamp_hourly', inplace=True)
    # Create a complete timestamp range
    full_index = pd.date_range(start=df_hourly.index.min(), end=df_hourly.index.max(), freq='H')

    # Reindex DataFrame to include missing timestamps
    df = df_hourly.reindex(full_index)

    # Function to generate random values based on column statistics
    def generate_random_values(series):
        return np.random.normal(series.mean(), series.std(), series.isna().sum())

    # Fill missing values with random values following column patterns
    for column in df.columns:
        df.loc[df[column].isna(), column] = generate_random_values(df[column])

    # Reset index to make timestamp a column again
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'timestamp'}, inplace=True)
    # Set timestamp as index
    df.set_index('timestamp', inplace=True)
    # List of columns to modify
    columns_to_modify = ['temperature', 'rainfall', 'leaf_wetness', 'humidity']
    # Replace negative values with 0 in selected columns
    df[columns_to_modify] = df[columns_to_modify].applymap(lambda x: abs(x) if x < 0 else x)
    return df['temperature']

def train_arima_model(data, order,seasonality_order):
    model = ARIMA(data, order=order,seasonal_order=seasonality_order)
    return model.fit()

def forecast(model_fit, steps=7):
    return model_fit.forecast(steps=steps)

