"""A fraud-review graph without agxai: the starting point of eval 1."""

from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class Review(TypedDict, total=False):
    amount: float
    score: float
    route: str


def risk_model(amount: float) -> float:
    return min(amount / 10_000, 1.0)


async def score(state: Review) -> Review:
    return {"score": risk_model(state["amount"])}


async def route(state: Review) -> Review:
    return {"route": "HUMAN_REVIEW" if state["score"] >= 0.8 else "AUTO_APPROVE"}


def build_graph():
    builder = StateGraph(Review)
    builder.add_node("score", score)
    builder.add_node("route", route)
    builder.add_edge(START, "score")
    builder.add_edge("score", "route")
    builder.add_edge("route", END)
    return builder.compile()


graph = build_graph()


if __name__ == "__main__":
    print(asyncio.run(graph.ainvoke({"amount": 9200.0})))
