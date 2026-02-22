# 🔌 ESGateway

## Inspiration
Built specifically for this hackathon, our core mission was simple: **to make building and working in the EU as seamless and attractive as possible.**

The European Union represents a massive, lucrative market, but its evolving labyrinth of ESG regulations—specifically CSRD, ESRS, and the EU Taxonomy—creates a daunting barrier to entry. Companies, whether they are local startups scaling within the EU or global enterprises trying to enter the market, often view these regulations as a roadblock rather than an opportunity. 

We wanted to change that narrative. Our inspiration was to build a tool that completely demystifies EU compliance, lowering the barrier to entry and making Europe a transparent, highly attractive place to do business. We built **ESGateway**—an engine that gives companies a definitive roadmap to compliance so they can focus on innovating rather than navigating red tape.

## What it does
ESGateway is a B2B consulting platform that automates **CSRD (Corporate Sustainability Reporting Directive)** compliance and **EU Taxonomy** alignment for European AI infrastructure and broader enterprise markets. 

The engine audits the gap between corporate sustainability claims and financial reality by cross-referencing mandatory disclosures against official financial reporting to quantify the "Say-Do Gap".

**A Score for Everyone, A Roadmap for the Future:**
Whether you are a non-EU company looking to enter the market, or an EU company already doing basic reporting, everyone gets a definitive compliance score and **Taxonomy Alignment Percentage** — one number that answers: *are you legally spending where you're promising?*



Crucially, ESGateway is predictive. For companies already in the EU, the system analyzes your current data against upcoming legislative phases. If your company is growing, the engine flags exactly what new legislation will apply to you next year (e.g., crossing the 250-employee or €40M turnover threshold) and provides the necessary steps to prepare before you are caught off guard.

## How we built it
We decoupled our frontend and backend using a strict TypeScript contract (`contracts/`), enabling rapid parallel development and a highly deterministic state machine. The frontend was built with **Next.js, TypeScript, and Tailwind CSS** for a clean, "Enterprise Modernist" interface.

### The Triad: A Purpose-Built AI Agent Workflow
To tackle the sheer density of EU financial and sustainability reporting, we moved beyond a simple LLM wrapper. Our Python LangGraph backend is powered by Anthropic Claude 3.5 Sonnet, orchestrated as a team of three specialized **AI Agents**. By dividing the cognitive load, we eliminate agent ambiguity.

1. **The Extractor Agent (The Data Miner):** Ingests unstructured corporate PDFs. Utilizing prompt caching and strict XML-tagging, it isolates exact CapEx figures and company sizing metrics. 
2. **The Scorer Agent (The Strict Auditor):** Cross-references the Extractor's data directly against our typed JSON regulatory database to objectively calculate current compliance.
3. **The Advisor Agent (The Strategic Consultant):** Analyzes the compliance gaps and generates a concrete roadmap to achieve alignment and unlock the European market.



### Live EU Legal Knowledge Base
To ensure clear adherence to strict EU standards, we built a live **Regulatory Knowledge Base** underpinned by a strictly typed, version-controlled JSON schema.


## Challenges we ran into

1. **The "Cold Start" Market Pivot:** Initially, we only built the system to ingest and analyze highly structured data and existing 100+ page ESG reports. However, we quickly realized there was a massive market segment—SMEs and non-EU companies looking to enter the market—who *don't have these documents yet*. We had to rapidly redesign our input layer and Advisor Agent to guide companies from a blank slate, offering predictive roadmaps based purely on their basic company metrics (revenue, headcount, sector).
2. **From ESG "Advice" to Strict "Compliance":** Mid-hackathon, we completely pivoted the output of our Advisor Agent. We started by trying to generate broad "ESG strategy advice," but realized LLMs can easily drift into subjective, hallucinated corporate jargon. We shifted to generating strict **compliance advice**. LLMs are incredibly powerful at deterministic rule-following (checking user states against our JSON legal schema) rather than inventing green strategies, so we aligned our product to fit the actual strengths of the technology.
3. **Double Materiality Mapping:** Accurately mapping financial data to ESRS double materiality requirements required deep prompt engineering to ensure our agents understood the difference between financial risk (outside-in) and environmental impact (inside-out).



## Accomplishments that we're proud of
We are incredibly proud of building a **deterministic AI system**. By forcing the LLM to interact with a strictly typed JSON database representing EU law, we removed "agent ambiguity." We didn't just build a chatbot that talks about sustainability; we built a rigorous compliance engine that cites specific articles, thresholds, and financial penalties without hallucinating.

## What we learned
* **The Power of Multi-Agent Orchestration:** Moving from a single prompt to a LangGraph workflow with designated personas drastically reduced errors and improved analytical depth.
* **Structuring for AI:** The best way to make an AI system reliable is to feed it highly structured, typed data rather than expecting it to accurately parse legal PDFs on the fly.
* **Regulatory Nuance:** We gained a profound understanding of the EU Taxonomy's 6 environmental objectives, and how EU legislation scales dynamically based on a company's growth trajectory.



## What's next for ESGateway

* **Holistic ESG Compliance:** Expanding our knowledge base and rule engine beyond just environmental sustainability (the "E") to cover the full spectrum of Social and Governance directives. This includes integrating upcoming regulations like the Corporate Sustainability Due Diligence Directive (CS3D) for supply chain monitoring and labor rights.
* **Continuous Compliance Monitoring:** Transitioning from a one-off audit tool to a dynamic, always-on engine. Companies will be able to continuously upload quarterly financials, cap tables, or live operating metrics, receiving real-time alerts and updated recommendations the moment they approach new regulatory growth thresholds.
* **Multi-Modal Data Ingestion:** Upgrading our Extractor Agent to handle multi-modal inputs. We want to allow companies to upload not just text PDFs, but raw ERP data dumps (Excel/CSV), images of manufacturing facilities, and even audio transcripts from stakeholder meetings for a much richer Double Materiality assessment.
* **Refined Scoring Mechanisms:** Enhancing our mathematical models to include sector-specific benchmarking, allowing companies to see not only their own "Say-Do Gap" but also how their taxonomy alignment compares against anonymized industry peers within the EU.
* **Automated Report Generation:** Moving beyond generating strategic advice to actually generating the compliance artifacts themselves. We plan to output draft, legally-formatted XHTML and iXBRL-tagged reports ready for direct submission to national registries and the upcoming European Single Access Point (ESAP).