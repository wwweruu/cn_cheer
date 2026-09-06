import { useSyncExternalStore } from "react";
import { runtimeAssets } from "../assets/runtimeAssets";

export function AssetLoadingStatus() {
  useSyncExternalStore(runtimeAssets.subscribeAll, runtimeAssets.version, runtimeAssets.version);
  const { total, ready, loading, failed } = runtimeAssets.stats();
  if (!loading && !failed) return null;
  return <div className="asset-loading-status" role="status" data-loading={loading} data-failed={failed}>
    {loading > 0 && <span>战场载入 {ready}/{total}</span>}
    {failed > 0 && <><span>{failed} 项外观暂不可用</span><button type="button" onClick={runtimeAssets.retryFailures}>重试外观</button></>}
  </div>;
}
