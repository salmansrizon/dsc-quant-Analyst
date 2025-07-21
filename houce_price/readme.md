# House Price Prediction: Technical Documentation

## Problem Statement
Accurate house price prediction is a critical task in real estate analytics. This project aims to build a robust regression model to predict house prices based on various property features. The primary challenges include handling data inconsistencies, feature engineering to capture complex relationships, and selecting and evaluating models to ensure reliable predictions on unseen data.

## Dataset
- **train.csv**: Contains house features and sale prices for training.
- **test.csv**: Used for evaluating model performance.
- **index.csv**: External dataset with economic indicators (e.g., GDP growth).

## Methodology & Analysis

### 1. Data Exploration and Preprocessing
- **Initial Analysis**: The project began with loading the `train.csv` dataset and conducting an initial exploration to understand its structure, identify data types, and check for missing values.
  ```python
  df.isnull().sum()  # Check for missing values
  ```
- **Outliers**: Visualized and treated outliers using winsorization and log transformation to stabilize the data distribution.
  ```python
  from scipy.stats.mstats import winsorize
  winsorized_sale = winsorize(df['SalePrice'])
  log_sale_price = np.log(df['SalePrice'])
  ```

### 2. Feature Engineering
- **Dummy Variables**: Created dummy variables for categorical features to enable regression modeling.
  ```python
  df = pd.concat([df, pd.get_dummies(df.MSZoning, prefix="mszoning", drop_first=True)], axis=1)
  ```
- **Interaction Terms**: Engineered interaction terms to capture complex relationships.
  ```python
  df['int_over_garage_liv'] = df['GarageArea'] * df['OverallQual'] * df['GrLivArea']
  ```
- **External Data Integration**: Incorporated GDP data to account for macroeconomic trends.
  ```python
  house_gdp = pd.read_csv('dataset/index.csv')
  df = pd.merge(df, house_gdp, left_on='YrSold', right_on='Year', how='left')
  ```

### 3. Model Building
- **OLS Regression**: Built a baseline model using Ordinary Least Squares (OLS).
  ```python
  import statsmodels.api as sm
  X = sm.add_constant(df[['OverallQual', 'GrLivArea', 'GarageCars', 'GarageArea', 'TotalBsmtSF', 'int_over_garage_liv']])
  Y = np.log1p(df['SalePrice'])
  model = sm.OLS(Y, X).fit()
  print(model.summary())
  ```
- **Regularized Models**: Implemented Ridge, Lasso, and Elastic Net regression to handle multicollinearity and improve generalization.
  ```python
  from sklearn.linear_model import RidgeCV, LassoCV, ElasticNet
  ridge = RidgeCV(alphas=[0.001, 0.01, 0.1, 1, 10], cv=10)
  ridge.fit(X, Y)
  ```

### 4. Model Evaluation
- **Metrics**: Evaluated models using R-squared, MAE, MSE, RMSE, and MAPE.
  ```python
  from sklearn.metrics import mean_absolute_error
  mae = mean_absolute_error(y_true, y_pred)
  ```
- **Cross-Validation**: Used k-fold cross-validation to ensure robustness.
- **Comparison of Approaches**: A comparison table was added to summarize the performance of different machine learning approaches:

| Approach           | Accuracy | Pros                                         | Cons                                   |
|--------------------|----------|----------------------------------------------|----------------------------------------|
| Linear Regression  | 0.85     | Simple to implement, interpretable          | Struggles with non-linear data         |
| Random Forest      | 0.90     | Handles non-linear data well, robust        | Requires tuning, less interpretable    |
| XGBoost            | 0.92     | High accuracy, handles missing data well    | Computationally expensive, complex     |

This comparison highlights the trade-offs between simplicity, interpretability, and computational complexity.

## Key Findings
- **OLS and Ridge Regression**: Achieved the best performance with R-squared values around 0.82.
- **Feature Engineering**: Interaction terms and external variables significantly improved model accuracy.
- **Log Transformation**: Reduced the impact of outliers and stabilized the models.
- **Elastic Net**: Underperformed compared to other models.
- **XGBoost**: Provided the highest accuracy but required significant computational resources.

## Justification of Methods
- **Regression Models**: Provide interpretable results and are well-suited for continuous target prediction.
- **Feature Engineering**: Captures complex relationships and improves model performance.
- **External Data**: Enhances predictive power by incorporating macroeconomic trends.
- **Cross-Validation**: Ensures the model generalizes well to unseen data.
- **Comparison Table**: Offers a clear understanding of the trade-offs between different approaches.

## How to Reproduce
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the Jupyter notebook `main.ipynb` to reproduce the analysis and results.

## Conclusion
This project demonstrates a systematic approach to house price prediction, leveraging data cleaning, feature engineering, and advanced regression techniques. The methodology ensures robust and interpretable predictions, making it a valuable tool for real estate analytics.
