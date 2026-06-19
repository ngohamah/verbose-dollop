# Last Mile Delivery Auditor — Veridi Logistics

## A. Executive Summary

Analysis of 96,470 Olist Brazilian e-commerce orders (2016–2018) reveals that while **91.9% of deliveries arrive on time**, the 8.1% that don't cause severe reputational damage: Super Late orders (>5 days late) score **2.3★ vs 4.3★** for on-time deliveries — a 47% drop in customer satisfaction that directly explains the CEO's observed spike in negative reviews. The problem is **not nationwide**: remote northern states (AM, RR, AP) suffer late rates 3–4× higher than São Paulo hub states, confirming that estimated delivery dates systematically over-promise for last-mile distances the logistics network cannot reliably meet. The root cause is structural — delivery date estimates do not adequately account for the distance from the São Paulo distribution centre to Brazil's remote regions — and fixing promise accuracy (not physical logistics) would recover most of the customer satisfaction gap.

---

## B. Project Links

- **Dashboard:** [Last Mile Delivery Auditor on streamlit](https://verbose-dollop-iap4z67fcfrfdzaerks98a.streamlit.app/)
- **Notebook:** [`analysis.ipynb`](./analysis.ipynb) — Full analysis with all 4 user stories + bonus
- **Presentation:** [`Last Mile Delivery Presentation`](https://docs.google.com/presentation/d/11uuHmh-YYqNdtBzDfbH_H6XgtZjKWF5zTNrhg-XZ0cU/edit?usp=sharing)

---

## C. Technical Explanation

### Data Cleaning

1. **Schema joining (Story 1):** Orders, Reviews, Customers, Products, and Order Items were joined using left merges on `order_id` and `customer_id`. To prevent the 1-to-many row explosion common with review and item joins, reviews were aggregated to one row per order (mean review score) and only the first item per order was retained for category lookup before merging.

2. **Delay calculation (Story 2):** `Days_Difference = order_estimated_delivery_date − order_delivered_customer_date`. Positive values indicate early delivery (on time); negative values indicate late delivery. Orders with `order_status` of `canceled` or `unavailable` were excluded, as they have no delivery date and would skew the delay distribution. Orders without a delivered date (not yet delivered at snapshot time) are flagged as "Not Delivered" and excluded from percentage calculations.

3. **Classification thresholds:** On Time (≥0 days), Late (−1 to −5 days), Super Late (<−5 days) — matching the project acceptance criteria exactly.

4. **Category translation (Bonus):** Portuguese category names were mapped to English using the `product_category_name_translation.csv` file included in the Olist dataset. Categories without a mapping were left as-is (these represent a small minority of orders).

### Candidate's Choice Addition: Monthly Delivery Performance Trend

**What it is:** A time-series chart showing monthly on-time %, late %, and average review score from 2016 to 2018.

**Why it matters to the business:** The CEO noticed a *spike* in negative reviews but didn't know if it was a new problem or always present. This chart reveals the trend direction — whether late delivery rates are worsening over time (operational drift during growth) or stable (structural). It also exposes **seasonality**: volume spikes (e.g., Black Friday / holiday season in Nov–Dec) that correlate with temporary drops in on-time rate, giving Operations a predictive signal to pre-position inventory before peak periods.

---

## Stack

- **Language:** Python 3.11
- **Dashboard:** Streamlit
- **Analysis:** pandas, numpy, plotly
- **Data:** Olist Brazilian E-Commerce Public Dataset (Kaggle)

## Run Locally

```bash
pip install -r streamlit-dashboard/requirements.txt
streamlit run streamlit-dashboard/app.py
```
## Demo
![Dashboard](https://verbose-dollop-iap4z67fcfrfdzaerks98a.streamlit.app/)

## Data Files

CSV files are in the same directory for easy testing and evaluation from instructors. I did NOT commit the files to git (they are gitignored). Please match file names!
