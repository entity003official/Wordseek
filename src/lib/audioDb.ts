const DB_NAME = 'beyond-words-audio'
const STORE_NAME = 'recordings'

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1)
    request.onupgradeneeded = () => request.result.createObjectStore(STORE_NAME)
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function saveAudio(key: string, blob: Blob) {
  const db = await openDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite')
      transaction.objectStore(STORE_NAME).put(blob, key)
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error || new Error('保存录音事务已取消'))
    })
  } finally {
    db.close()
  }
}

export async function getAudioUrl(key?: string) {
  if (!key) return null
  const blob = await getAudioBlob(key)
  return blob ? URL.createObjectURL(blob) : null
}

export async function getAudioBlob(key?: string) {
  if (!key) return null
  const db = await openDb()
  try {
    const blob = await new Promise<Blob | undefined>((resolve, reject) => {
      const request = db.transaction(STORE_NAME).objectStore(STORE_NAME).get(key)
      request.onsuccess = () => resolve(request.result as Blob | undefined)
      request.onerror = () => reject(request.error)
    })
    return blob ?? null
  } finally {
    db.close()
  }
}

export async function deleteAudio(key?: string) {
  if (!key) return
  const db = await openDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite')
      transaction.objectStore(STORE_NAME).delete(key)
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error || new Error('删除录音事务已取消'))
    })
  } finally {
    db.close()
  }
}

export async function clearAudio() {
  const db = await openDb()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction(STORE_NAME, 'readwrite')
      transaction.objectStore(STORE_NAME).clear()
      transaction.oncomplete = () => resolve()
      transaction.onerror = () => reject(transaction.error)
      transaction.onabort = () => reject(transaction.error || new Error('清理录音事务已取消'))
    })
  } finally {
    db.close()
  }
}
