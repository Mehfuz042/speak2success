/**
 * Head-steadiness scoring for the live coach.
 *
 * A single frame can look perfectly centred while the candidate is nodding or
 * turning, so steadiness is judged over a short rolling window of yaw/pitch
 * samples instead of one frame. Samples older than HEAD_WINDOW_MS are ignored,
 * which keeps brief face-detection gaps from counting as movement.
 *
 * Kept framework-free so it can be unit tested with plain Node.
 */

export const HEAD_WINDOW = 10 // max samples (~2s at 5 fps)
export const HEAD_WINDOW_MS = 2500
export const HEAD_YAW_SPREAD_MAX = 8
export const HEAD_PITCH_SPREAD_MAX = 6
// Facing gate for the windowed check (a little wider than eye-contact).
export const HEAD_FACING_YAW_MAX = 25
export const HEAD_FACING_PITCH_MAX = 20
// Stricter per-frame fallback used until the window has enough samples.
const FALLBACK_YAW_MAX = 15
const FALLBACK_PITCH_MAX = 12
const MIN_SAMPLES = 4

/**
 * @param {{yaw:number|null, pitch:number|null}} angles
 * @param {Array<{yaw:number, pitch:number, at:number}>} headHistory mutated in place
 * @param {number} [now] timestamp in ms (injectable for tests)
 * @returns {boolean} true when the head is facing the camera and steadily held
 */
export function temporalHeadSteady(angles, headHistory, now = performance.now()) {
  const yaw = angles?.yaw
  const pitch = angles?.pitch
  const facing = (
    yaw != null &&
    pitch != null &&
    Math.abs(yaw) <= HEAD_FACING_YAW_MAX &&
    Math.abs(pitch) <= HEAD_FACING_PITCH_MAX
  )
  if (!headHistory || yaw == null || pitch == null) return false

  headHistory.push({ yaw, pitch, at: now })
  while (headHistory.length > HEAD_WINDOW) headHistory.shift()
  while (headHistory.length && now - headHistory[0].at > HEAD_WINDOW_MS) headHistory.shift()

  if (headHistory.length < MIN_SAMPLES) {
    return facing && Math.abs(yaw) <= FALLBACK_YAW_MAX && Math.abs(pitch) <= FALLBACK_PITCH_MAX
  }

  const yaws = headHistory.map((sample) => sample.yaw)
  const pitches = headHistory.map((sample) => sample.pitch)
  const yawSpread = Math.max(...yaws) - Math.min(...yaws)
  const pitchSpread = Math.max(...pitches) - Math.min(...pitches)
  return facing && yawSpread <= HEAD_YAW_SPREAD_MAX && pitchSpread <= HEAD_PITCH_SPREAD_MAX
}
