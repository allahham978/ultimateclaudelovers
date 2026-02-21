# ESG Accountability Engine: The "Say-Do Gap" Auditor

## The Purpose
The ESG Accountability Engine is an automated forensic auditing tool designed to combat corporate greenwashing. It solves a specific, high-stakes problem: companies often publish glossy sustainability reports (the "Say") that do not mathematically align with their actual financial spending (the "Do").

Instead of forcing users to manually cross-reference 100-page PDFs against complex balance sheets, this application automates the entire process. By calculating the gap between public claims and actual capital expenditure, it delivers immediate, verifiable ROI for compliance officers, retail investors, and financial analysts.

## Overall Architecture & Components
This system is built as a cleanly engineered website that isn't doing too much. It focuses strictly on executing its core function flawlessly. It consists of three main components:

* **The Multi-Agent Backend:** An autonomous system of specialized AI workers that read documents, fetch financial data, and synthesize the findings without requiring rigid, brittle code.
* **The Analysis Engine:** The translation layer that converts subjective corporate text into measurable financial metrics, ultimately calculating a definitive "Greenwashing Risk Score."
* **The Minimalist Interface:** A highly focused frontend that requires zero learning curve. It takes a ticker and a PDF as inputs and immediately returns a side-by-side comparative ledger.

## The AI Agents (How They Work Together)
The backend relies on three specialized AI agents working collaboratively to evaluate the data.

* **The Extractor (The Reader):** This agent reads the uploaded ESG report. It ignores the marketing fluff and specifically extracts forward-looking sustainability promises and capital commitments.
* **The Fetcher (The Data Gatherer):** Operating in parallel, this agent queries external financial databases. It autonomously writes and executes small commands to retrieve the exact Capital Expenditure (CapEx) and operational costs for that specific company.
* **The Auditor (The Orchestrator):** This agent manages the entire workflow. It receives the extracted text from the Reader and the hard numbers from the Fetcher. It cross-references the two, mathematically verifies the discrepancies, and formats the final data to be sent to the user interface.

If the Fetcher hits a dead end (like a missing financial data point), the Auditor autonomously instructs it to try a different proxy metric, ensuring the system gracefully adapts instead of crashing.

## UI & Data Flow
The philosophy for the frontend is that less is better. The application entirely avoids cluttered dashboards in favor of a stark, side-by-side ledger.

When the backend agents complete their audit, the data flows directly into the UI. We keep the color in it specifically to drive the data narrative: crisp greens highlight verified financial alignment, while stark reds instantly expose the "Say-Do" discrepancies. This functional design ensures the user instantly understands the risk score and the ROI of the tool the second the page renders.