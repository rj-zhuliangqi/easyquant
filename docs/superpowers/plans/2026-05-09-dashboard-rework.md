# Dashboard Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the monitoring dashboard so the main comparison chart is normalized from the first intraday sample, the selected-sector workspace feels immediate, and sector stock panels degrade gracefully when live pull fails.

**Architecture:** Keep rankings and board snapshots as the core cached dataset, add one combined sector workspace API for fast detail/history reads, and treat sector stocks as a slower auxiliary stream with explicit status metadata. The frontend becomes a three-zone app: monitor rail, comparison canvas, and selected-board workspace plus market-wide ranking.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, pandas, vanilla JS, ECharts, pytest

---
