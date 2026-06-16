import { useQuery } from '@tanstack/react-query'
import { dataRegistry } from '../data/registry'

export function useDataRef<T = unknown>(uri: string | undefined) {
  return useQuery<T>({
    queryKey: ['dataRef', uri],
    enabled: !!uri,
    queryFn: async () => {
      if (!uri) throw new Error('no uri')
      return (await dataRegistry.resolve(uri)) as T
    },
  })
}
