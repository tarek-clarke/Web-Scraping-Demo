# Resilient Web Scraper Prototype (Visual Extraction)

## Overview
This is a Proof-of-Concept for a **Visual Heuristic Extraction** system using R and `chromote`. Unlike traditional scrapers that rely on brittle CSS selectors (e.g., `#price_block`), this script renders the page and uses **Computed Styles** to identify pricing data based on visual hierarchy (font size and location).

## Core Logic
1.  **Headless Rendering:** Uses Chrome DevTools Protocol to render the full DOM.
2.  **Visual Scan:** Scans all text nodes for currency patterns.
3.  **Heuristic Selection:** Selects the price based on:
    * Font Size (Prioritizes largest elements)
    * Viewport Position (Prioritizes elements 'above the fold')
    * Semantic Labeling (Proximity to "Buy" keywords)

## Usage
```r
# Install dependencies
install.packages("chromote")

# Run the extraction
source("scraper.R")
