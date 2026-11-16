"""Build the two one-page submission PDFs with the bundled document runtime."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
W,H=595,842


def start(name,title):
    c=canvas.Canvas(str(ROOT/'docs'/name),pagesize=(W,H))
    c.setFillColorRGB(1,1,1);c.rect(0,0,W,H,fill=1,stroke=0)
    c.setFillColor(HexColor('#132d46'));c.rect(0,H-100,W,100,fill=1,stroke=0)
    c.setFillColorRGB(1,1,1);c.setFont('Helvetica-Bold',22);c.drawString(36,H-48,title)
    c.setFont('Helvetica',10);c.drawString(36,H-72,'Credit Risk Portfolio | Synthetic data | Python 3.11')
    return c


def block(c,y,title,text):
    style=ParagraphStyle('body',fontName='Helvetica',fontSize=10,leading=14,textColor=HexColor('#25384a'))
    c.setFillColor(HexColor('#126b76'));c.setFont('Helvetica-Bold',12);c.drawString(36,y,title)
    p=Paragraph(text,style);_,height=p.wrap(W-72,700);p.drawOn(c,36,y-10-height)
    return y-height-36


c=start('solution_overview.pdf','Solution overview')
y=714
for title,text in [
('Analyst workflow','Portfolio: compare income, employment, region, age and product; filter and inspect relative loan-age repayment trends. Account: inspect score, baseline drivers and payments. Anomaly review: inspect evidence, confirm/dismiss and save notes with history. Ask the Portfolio: ask a supported question and verify the plan, figures and SQL.'),
('AI feature 1 - grounded portfolio questions','Trigger: analyst submits a question. NeMo input rails invoke a Guardrails AI policy validator; LangGraph calls OpenAI through LiteLLM for a Pydantic plan. Guardrails AI validates output; parameterized DuckDB SQL supplies all figures. Human step: verify plan, filters and evidence. False positive: incorrect interpretation; false negative: answerable request declined. One-hour exact caching, request/token quotas and bounded execution reduce usage. Langfuse metadata/token tracing is verified; raw questions and answers are excluded.'),
('AI feature 2 - anomaly review','Trigger: batch refresh. Rules detect DPD deterioration, falling payment ratios and high peer utilization; Isolation Forest flags unusual combinations. 1,747 accounts flagged (11.9%). False positive: legitimate unusual behaviour; false negative: problematic pattern missed. Analysts confirm/dismiss with notes. SQLite retains local history; hosted storage needs a durable volume. No anomaly ground-truth accuracy claim.'),
('Default models and results','Customer-group train/validation/test split, approximately 60/20/20; preprocessing fits training only. Logistic regression selected by validation AUC. Test: AUC <b>0.6784</b>, KS <b>0.2660</b>, Gini <b>0.3568</b> (2,968 accounts). Histogram boosting: 0.6700 / 0.2644 / 0.3399. Validation permutation importance and baseline local coefficients explain model reliance. Monitor drift, missingness, calibration and matured-label performance.'),
('Top three portfolio insights','Overall observed default rate: 16.10% (2,364/14,685). Under-$30k income: 38.67% (174/450); review affordability. Unemployed: 34.96% (251/718); prioritize review. Combined under-$30k/unemployed: 44.30% (101/228); inspect this segment before policy changes. These are descriptive associations.'),
('Assumptions and production needs','No default date/horizon: retrospective demonstration, not validated future PD. Collections excluded; other snapshot timing remains unverified. Latest balances are not synchronized exposure. Bank teams must supply point-in-time data, outcome definitions, secure access, API funding/spend controls, durable review/quota storage, monitoring and model approval. Optional local read-only MCP exposes tools to external clients; dashboard uses direct calls. Public hosting, repository and video publication remain pending.')]:
    y=block(c,y,title,text)
assert y>25,y
c.save()
c=start('architecture.pdf','Architecture and data flow')
y=710
stages=[('1  RAW DATA','Five unchanged CSVs: customers, loan accounts, bureau lines, monthly repayments, collections events.'),
('2  INGESTION AND VALIDATION','pandas / NumPy: key and range checks, missingness flags, label normalization, aggregate child tables before joining. One row per account; financial reconciliation and source hashes.'),
('3  ANALYTICAL DATA','Parquet + DuckDB: 14,685 account rows; separate customer, bureau, event and monthly tables. Account-grain profiles, cross-segments, original lending and latest recorded balances.'),
('4  MODELS AND ANOMALIES','scikit-learn: logistic regression + histogram gradient boosting; customer-group holdouts, training-only preprocessing, permutation importance. Isolation Forest + history/peer rules; versioned flags and evidence.'),
('5  DASHBOARD','Streamlit + Plotly: portfolio filters, account scores and drivers, loan-age trends, anomaly review queue. Cached data keyed by artifact versions.'),
('6  ASK THE PORTFOLIO','Question -> NeMo input rail + Guardrails AI validator -> exact cache / SQLite quotas -> LangGraph -> LiteLLM -> OpenAI query plan -> Pydantic + Guardrails AI -> DuckDB SQL -> deterministic answer and evidence. LLM receives question + category vocabulary, no account rows or computed figures. Langfuse records model metadata/token usage, excluding raw input/output.'),
('7  HUMAN REVIEW AND STORAGE','Analyst verifies Q&A plan/evidence; anomaly confirm/dismiss + note -> append-only SQLite history (account, detector version, reviewer, timestamp). Durable mounted storage required for hosted persistence.')]
for i,(title,text) in enumerate(stages):
    y=block(c,y,title,text)
    if i<len(stages)-1:
        c.setStrokeColor(HexColor('#126b76'));c.line(W/2,y+16,W/2,y+5);c.line(W/2,y+5,W/2-4,y+10);c.line(W/2,y+5,W/2+4,y+10)
        y-=8
y=block(c,y,'Optional MCP and deployment boundary','Official MCP SDK: local stdio tools for approved queries, account summaries, anomaly lists and model metrics; read-only, protocol-tested, no public endpoint. Dashboard uses direct calls. GitHub + pinned dependencies -> Streamlit/Docker hosting; server-side secrets and durable SQLite volumes required. Local quotas are not a dollar spending cap. Publish dashboard/repository/video; maintain app for 14 days.')
assert y>20,y
c.save()
for name in ['architecture.pdf','solution_overview.pdf']:
    assert len(PdfReader(ROOT/'docs'/name).pages)==1
    print(name,'one page verified')
