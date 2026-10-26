import asyncio, csv, json, time
from pathlib import Path
import llm

HERE = Path(__file__).parent
model = llm.get_async_model("openrouter-decisions/typesafe/jev-1.14")
QUESTION = "The publication is about the transparency of governments or public administrations."

async def ask(row, sem):
    async with sem:
        response = model.prompt(row["title"], system=QUESTION)
        p = json.loads(await response.text())["noul"]
        cost = (await response.json())["usage"]["cost"]
        return {**row, "p": p}, cost

async def main():
    rows = list(csv.DictReader(open(HERE / "publications.csv")))
    sem = asyncio.Semaphore(8)
    start = time.perf_counter()
    results = await asyncio.gather(*(ask(row, sem) for row in rows))
    seconds = time.perf_counter() - start
    scored = sorted((r for r, _ in results), key=lambda r: r["p"], reverse=True)
    with open(HERE / "publications_scored.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["p", "title", "doi"])
        writer.writeheader()
        writer.writerows(scored)
    cost = sum(c for _, c in results)
    print(f"{len(rows)} titles in {seconds:.1f} seconds, ${cost:.5f}")

asyncio.run(main())
