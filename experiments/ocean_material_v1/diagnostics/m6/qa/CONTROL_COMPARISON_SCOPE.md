# Fresh-process inventory comparison scope

The first offline comparison found matching animal, scene hashes, camera matrices, global settings, bindings and image tolerances. The complete product inventory differed only in `viewPickingId`: the old process reported 10172534858793929162 and the fresh process 6930758660756584125.

The RGB/HDR capture comparison therefore retains both complete inventories and reports this process/view picking identity separately. It excludes **only `render_product.viewPickingId`** from effective-render-control equality, while comparing every camera attribute and every other product/global setting with the existing `same_settings` function. It does not assert equality of picking results, object-ID outputs or visible masks. Image thresholds and scene-state checks are unchanged; the failed first analysis record is preserved.

NVIDIA's [UsdContext picking API](https://docs.omniverse.nvidia.com/kit/docs/omni.usd/1.12.2/_build/docs/omni.usd/latest/classomni_1_1usd_1_1UsdContext.html) identifies `ViewPickingId` with picking for a specific view. Treating this changing view identifier separately is an audit-scope decision for these RGB/HDR outputs, not evidence that a sampling or lighting difference can be ignored.
