`gamma_insar` maintains various log files while processing a stack, these files are held within the stack's `job directory`.
This document briefly covers "part" of the *common* logging structure of a stack, however does *not* cover event-specific logging properties (specific logged events have a lot of special case properties that don't apply to any other event).

## Logging file structure ##

The log files are split into various levels of verbosity described below:
 * `insar-log.jsonl` - This is the most comprehensive log file `gamma_insar` produces, it has a complete sequence of every single GAMMA command run while processing, as well as a few additional messages about how parts of the code are being processed / where settings are sourced / etc - all formatted in JSONL so it's machine readable.
 * `status-log.jsonl` - This is a summary of the status of the stack processing, it has very small/succinct messages about what is being processed, a manifest of the beginning/success/failure of all PRODUCTS (as opposed to python/Luigi tasks) that are being processed, plus additional information that may be useful to the user - this is in JSONL but is so succinct/small that it's also human readable and intended for humans to be able to easily identify where a processing job is and/or how it failed.
 * `luigi-interface.log` - The standard Luigi output log, it has info about all the tasks that were run, how they were scheduled, and if they succeeded/failed.
 * `task-log.jsonl` - Contains a comprehensive sequence of every single task that succeeded and/or failed, this is a strictly JSONL structured equivilent of what `luigi-interface.log` is more or less...

## JSON-L logged event properties ##

We only formally attempt to specify `insar-log.jsonl` and `status-log.jsonl` (and even then, only partially) - so far as to have a well-defined means for parsing the entries and identifying the status (good entries vs. warnings vs. errors) and what scene/product they belong to.  From this it's possible to determine what products have succeeded, if any had issues (and how severe they were) - to get further information the user must read event-specific properties which are not defined in the documentation formally (but are simple enough to identify/understand without documentation).

Both `insar-log.jsonl` and `status-log.jsonl` entries MAY have the following properties, and if they do they MUST match the definition below:
 * The `event` property defines the reason for the entry, this is human description with no spec.
 * The `level` property defines the type of event that is being logged, it MUST be "info", "warning", or "error".
 * The `timestamp` property defines the time the entry was logged (following JSON date time formatting standards)
 * The `scene` property defines an actual SLC scene (or acquisition) file the event is referring to, this is typically 'before' the final date-wide mosaics are produced.
 * The `scene_date` property defines the YYYYMMDD date of the product being referred to.
 * The `polarisation` property defines what polarisation the product being referred to is for, it MUST either be a single string, or an array of strings of "VV", "VH", "HH", or "HV".
 * For coregistration & interferogram related events the `primary_date` and `secondary_date` are used instead of `scene_date` above, their definition is the same.

`insar-log.jsonl` alone also has additional standardised entries that log all GAMMA calls made, these have the following properties:
 * The `cmd` property contains the GAMMA program being executed.
 * The `args` property contains an array of the command line args passed to the GAMMA call that was made.
 * The `cerr` and `cout` properties contain an array of line entries of their standard error/outputs perspectively.
