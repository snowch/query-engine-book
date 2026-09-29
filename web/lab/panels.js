// Every experiment's drawing, by name: what a lab block, or an edit's result, is drawn with.

import { mountBranches } from "./branches.js";
import { mountGather } from "./gather.js";
import { mountPlan } from "./plan.js";
import { mountPruning } from "./pruning.js";

export const EXPERIMENTS = {
  plan: mountPlan, gather: mountGather, pruning: mountPruning, branches: mountBranches,
};
