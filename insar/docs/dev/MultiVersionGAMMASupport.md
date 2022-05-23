This document describes the approach taken by `gamma_insar` to support multiple versions of GAMMA in a single code base.


## Problem Statement ##

GAMMA provides a set of programs for users to process SAR data acquisitions into higher level products such as backscatter and accurate interferometry, these programs are meant for manual use by humans using the command line (or a GUI wrapper), however `gamma_insar` uses GAMMA like an API.

Due to the nature of GAMMA's usage patterns they don't maintain anything quite like "API" stability, so programs can have their names changed and/or arguments re-ordered and re-named.  Additionally, like all software as new versions are produced some parts of the software become deprecated and are removed over time as well.

`gamma_insar` itself is currently written against a specific version of GAMMA (20191203) however there is desire to use newer versions of GAMMA which provide various quality improvements / bug fixes / etc.

The problem is "how" do we update `gamma_insar` in such a way that we can easily support running the workflow with support for multiple versions of GAMMA without having to re-write the code base every time we want to try a new version, eg: some kind of abstraction layer.

## Proposed Solution ##

My preferred solution is to continue building the code base on a fixed version of GAMMA (20191203) initially, but calling GAMMA through an additional layer of abstraction which lets us maintain a stable API by overriding functions with custom wrappers/implementations that do the appropriate version-specific logic under the hood if required.

This additional layer of abstraction would let us translate the old GAMMA API our code is written for, into the newer GAMMA API the proxy is built for.

This would require the least amount of code changes to existing processing modules as they can continue working like they currently do, and we just swap in different implementations of this proxy/translation layer if we run the workflow with a different version of GAMMA which translates our GAMMA-old intent into GAMMA-new logic.

In essence we would essentially be saying "GAMMA 20191203 is the minimum version we support", and then as new versions of GAMMA become available we evaluate the breaking changes and implement a proxy/translation layer for those areas of the API that have changed every time we need to support a new version without having to touch the greater `gamma_insar` code base **at all**.

## Alternative Solutions & why they weren't chosen ##

There are two obvious alternative solutions to supporting multiple versions of GAMMA:

1. Manually add different code paths into areas of the code base where and when GAMMA make breaking changes, which detect the currently running version of GAMMA and calls different version-dependent-logic directly in the area of code that makes the GAMMA calls.  Kind of like a bunch of if/else statements on the GAMMA version with different logic for each version of GAMMA.

2. Come up with our own (hopefully) stable API that wraps what we want GAMMA to do, and then implement different versions of that API for each version of GAMMA we want to support.


Method 1 above is the brute force approach, would require the most amount of code changes, and would end up getting messier and messier as we add support for more versions of GAMMA.  This isn't so much a "solution" as opposed to "just make it work when we hit problems each upgrade" - which is what we want to avoid.

Method 2 above is probably the most idealised solution, but it's harder to define all our future "intent" processing wise (thus unlikely we would actually ever manage to make a truly stable API as we can't predict the future) - I imagine we would end up just making our own API wrapper that doesn't truly give us any benefit over just using GAMMA's API itself (and working with the proposed solution to patch breaking changes in that API if/when we hit them).

The only potential future scenario I can see where the proposed solution will fail (and Method 2 would succeed) is if GAMMA completely re-wrote their whole software suite from scratch (leaving nothing of the old API remaining).  This seems unlikely however.

Regardless of any potential future where Method 2 might be required, the proposed solution is an interim stepping stone 'toward' Method 2 which would have been required anyhow, and definitely doesn't preclude us from adopting the approach of Method 2 in the future if the worst case scenario does eventuate.

Note: Method 2 would also be required if `gamma_insar` ever decided to support processing backends beyond GAMMA (but this seems way out of scope at this point in time / not worth considering in this proposal).

## Handling missing/removed programs ##

With the proposed solution, programs that get removed (or renamed) in a future GAMMA update would need to be re-implemented as a wrapper around whatever new functionality was added to GAMMA to support the same workflow.  In essence we would be implementing our own backward compatibility layer as we add support for new GAMMA versions, by supporting old functions with the new.

In cases where there is no way to truly implement the old functionality in it's entirety, we would need to evaluate what our processing requirement/intent for that function genuinely is (which should be a subset of the removed GAMMA program) and implement our own API for that subset of functionality using the newer GAMMA functions.

In an absolute worst case... where a program is removed and there is **no way** to implement the required functionality of it **at all** with the newer GAMMA version - we hit a brick wall that we would have hit no matter what method/solution we opted for - and we would need to seek alternative options for our processing workflow to work without that functionality, just as we would have even without supporting multiple GAMMA versions.

## Handling refactored program arguments ##

It's possible (and GAMMA has indeed done this) that function arguments will get re-ordered and/or re-named.

When this occurs for **required** arguments, the function will still need to be overridden in the proxy/translation layer to re-order the arguments (as these are represented as positional-required arguments in python) from the old 20191203 order/naming, to the newer GAMMA order/naming - however beyond this, the translation shouldn't require additional logic - it's simply forwarding the same arguments to the same function in a slightly different order.

When this occurs with **optional** arguments, the function will also still need to be overridden in the proxy/translation layer to do a name translation from the old-optional-argument-name to the new-optional-argument-name (as these are represented as optional-keyword arguments in python (eg: can **NOT** be passed as positional, and have a default value)).

## Handling missing/removed program arguments ##

In the event program arguments are removed from an existing function (which GAMMA has done with it's `ras*` programs, eg: to remove left/right mirroring support) there's three potential outcomes.

1. We don't use or require that functionality and there's no change required (since we never used that argument)
2. We do pass in that argument but we never used anything but the default / never really used that feature, in which case there's no change required (the new program lacking that optional argument would behave the same without it)
3. We do pass in that argument **and do use it**.  In this case we would need to override this function in the proxy/translation layer and find a way for us to implement that removed functionality another way (either through where ever it got moved to in GAMMA, or manually ourselves if it was removed entirely).
