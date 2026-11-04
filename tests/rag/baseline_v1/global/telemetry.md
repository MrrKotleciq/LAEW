---
name: Laboratory telemetry transport
title: Laboratory telemetry transport
description: Synthetic en retrieval fixture.
type: docs
scope: global
status: active
tags: [telemetry]
read_when:
  - Evaluating retrieval
---

## MQTT

MQTT QoS 1 provides at-least-once delivery. Deduplicate measurements using a stable message identifier.

## Modbus

A Modbus RTU frame uses a CRC to detect accidental transmission errors.
