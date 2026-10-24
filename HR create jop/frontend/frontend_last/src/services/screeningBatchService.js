import apiClient from "./apiClient";

/**
 * Submit a batch of CV files for asynchronous processing.
 * Endpoint: POST /jobs/{jobId}/screening-batches
 * Returns 202 Accepted with batch details.
 */
export async function createScreeningBatch({ jobId, files }) {
  if (!jobId) {
    throw new Error("A job must be selected before screening can start.");
  }
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file, file.name);
  }
  const { data } = await apiClient.post(`/jobs/${jobId}/screening-batches`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60000,
  });
  return data;
}

/**
 * Retrieve batch progress and items status.
 * Endpoint: GET /screening-batches/{batchId}
 */
export async function getScreeningBatch(batchId) {
  if (!batchId) {
    throw new Error("A batchId must be provided to fetch screening batch status.");
  }
  const { data } = await apiClient.get(`/screening-batches/${batchId}`);
  return data;
}

/**
 * Retry an eligible failed screening batch item.
 * Endpoint: POST /screening-batch-items/{itemId}/retry
 */
export async function retryBatchItem(itemId) {
  if (!itemId) {
    throw new Error("An itemId must be provided to retry.");
  }
  const { data } = await apiClient.post(`/screening-batch-items/${itemId}/retry`);
  return data;
}

/**
 * Retrieve recent screening batches for a job.
 * Endpoint: GET /jobs/{jobId}/screening-batches
 */
export async function getJobBatches(jobId, limit = 10) {
  if (!jobId) {
    return [];
  }
  const { data } = await apiClient.get(`/jobs/${jobId}/screening-batches`, {
    params: { limit },
  });
  return data;
}
