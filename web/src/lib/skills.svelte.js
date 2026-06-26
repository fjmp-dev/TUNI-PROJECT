// Shared smart-skill state. Freedrive deactivates an arm's trajectory controller,
// so the UR panel must disable that arm's move buttons while it's on.
export const freedrive = $state({ left: false, right: false });
