export function getJourneyHudState(state) {
  const reedCost = state.rules?.beacon_lumen_reed_cost || 3;
  const reeds = state.inventory.lumen_reed;
  const complete = state.beacon_awake;
  const currentStep = complete ? null : !state.mara_met ? 0 : reeds < reedCost ? 1 : 2;
  const completedMilestones = complete ? 3 : currentStep;

  let objective;
  let hint;
  let targetLabel;
  let target = null;

  if (complete) {
    objective = 'A signal answers beyond the valley';
    hint = 'A new signal has reached the valley. Listen for what answers.';
    targetLabel = 'SIGNAL CARRIED';
  } else if (!state.mara_met) {
    objective = 'Find Mara along the western path';
    hint = 'Speak with Mara to learn about the Listening Beacon.';
    targetLabel = 'MARA';
    target = state.mara;
  } else if (reeds < reedCost) {
    const needed = reedCost - reeds;
    objective = 'Gather Lumen reeds';
    hint = `Gather ${needed} more Lumen reed${needed === 1 ? '' : 's'} from the quiet patches.`;
    targetLabel = 'LUMEN REED';
    target = (state.reed_patches || []).reduce((nearest, patch) => {
      const distance = Math.hypot(patch.x - state.player.x, patch.y - state.player.y);
      return !nearest || distance < nearest.distance ? { patch, distance } : nearest;
    }, null)?.patch || null;
  } else {
    objective = 'Wake the Listening Beacon';
    hint = 'You have what the Beacon needs. Follow the eastern trail.';
    targetLabel = 'LISTENING BEACON';
    target = state.beacon;
  }

  const distance = target
    ? Math.hypot(target.x - state.player.x, target.y - state.player.y)
    : null;

  return {
    objective,
    hint,
    complete,
    currentStep,
    completedMilestones,
    progressPercent: completedMilestones / 3 * 100,
    reedCountText: `${Math.min(reeds, reedCost)} / ${reedCost}`,
    targetLabel,
    distanceText: distance === null
      ? complete ? 'Beyond the valley' : 'No patches remain'
      : `${distance.toFixed(1)} away`,
  };
}
