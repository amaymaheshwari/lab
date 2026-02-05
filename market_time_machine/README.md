# 📉 Market Time Machine

**Simulate history. Tesy your foresight.**

An interactive financial simulator that lets you invest in historical scenarios (Dot-Com Bubble, 2008 Crisis) and see if you can beat the market.

## 🚀 How to Run

1.  **Install Dependencies** (if not already):
    ```bash
    pip install flask
    ```
2.  **Start the App**:
    ```bash
    python app.py
    ```
3.  **Visit**: `http://127.0.0.1:5000`

## ⚙️ How it Works

*   **Curated Scenarios**: Data is loaded from `data/scenarios.json`.
*   **Scalability**: The `DataProvider` class in `app.py` is designed to be swapped. Currently uses `JsonDataProvider`, but can be upgraded to `PolygonApiProvider` to fetch real data from paid APIs.
*   **Tech Stack**: Flask, Chart.js, Vanilla CSS.

## 📂 Structure
*   `app.py`: Main logic + Data Layer.
*   `data/`: JSON datasets.
*   `static/`: Assets (CSS/JS).
*   `templates/`: HTML views.
