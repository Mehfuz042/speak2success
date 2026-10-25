import assert from 'node:assert/strict'
import {
  HEAD_PITCH_SPREAD_MAX,
  HEAD_WINDOW,
  HEAD_WINDOW_MS,
  HEAD_YAW_SPREAD_MAX,
  temporalHeadSteady,
} from '../src/lib/headSteadiness.js'

let passed = 0
function test(name, fn) {
  fn()
  passed += 1
  console.log(`ok ${passed} - ${name}`)
}

const centered = (offset = 0) => ({ yaw: 0 + offset, pitch: 0 })
const feed = (history, samples, start = 0, step = 200) =>
  samples.map((angles, index) => temporalHeadSteady(angles, history, start + index * step))

test('centred frame with no history passes the strict fallback', () => {
  const history = []
  assert.equal(temporalHeadSteady(centered(), history, 0), true)
  assert.equal(history.length, 1)
})

test('large yaw fails while the window is still short', () => {
  const history = []
  assert.equal(temporalHeadSteady({ yaw: 18, pitch: 0 }, history, 0), false)
  assert.equal(temporalHeadSteady({ yaw: 18, pitch: 0 }, history, 200), false)
  assert.equal(temporalHeadSteady({ yaw: 18, pitch: 0 }, history, 400), false)
})

test('steady but slightly turned head passes once the window fills', () => {
  const history = []
  const results = feed(history, [18, 18, 18, 18].map((yaw) => ({ yaw, pitch: 0 })))
  assert.equal(results.at(-1), true)
})

test('natural jitter inside the spread budget stays steady', () => {
  const history = []
  const yaws = [0, 3, -3, 2, -2, 1]
  const results = feed(history, yaws.map((yaw) => ({ yaw, pitch: 0 })))
  assert.equal(results.at(-1), true)
})

test(`yaw spread over ${HEAD_YAW_SPREAD_MAX} degrees is unsteady`, () => {
  const history = []
  const yaws = [0, 10, -10, 0]
  const results = feed(history, yaws.map((yaw) => ({ yaw, pitch: 0 })))
  assert.equal(results.at(-1), false)
})

test(`pitch spread over ${HEAD_PITCH_SPREAD_MAX} degrees is unsteady`, () => {
  const history = []
  const pitches = [0, 8, -8, 0]
  const results = feed(history, pitches.map((pitch) => ({ yaw: 0, pitch })))
  assert.equal(results.at(-1), false)
})

test('looking away fails regardless of a steady window', () => {
  const history = []
  const results = feed(history, [
    centered(0),
    centered(0),
    centered(0),
    { yaw: 40, pitch: 0 },
  ])
  assert.equal(results.at(-1), false)
})

test('null angles fail without mutating the window', () => {
  const history = []
  temporalHeadSteady(centered(), history, 0)
  const before = history.length
  assert.equal(temporalHeadSteady({ yaw: null, pitch: null }, history, 200), false)
  assert.equal(history.length, before)
})

test('samples older than the time window are pruned', () => {
  const history = []
  feed(history, [centered(0), centered(0), centered(0), centered(0)], 0)
  assert.equal(history.length, 4)
  temporalHeadSteady(centered(0), history, 600 + HEAD_WINDOW_MS + 1)
  assert.equal(history.length, 1, 'stale samples should be dropped before scoring')
})

test('the sample window never exceeds its cap', () => {
  const history = []
  const samples = Array.from({ length: HEAD_WINDOW + 5 }, () => centered(0))
  feed(history, samples)
  assert.equal(history.length, HEAD_WINDOW)
})

console.log(`\n${passed} checks passed`)
