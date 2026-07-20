import { beforeEach, vi } from 'vitest';
import type { AxiosInstance } from 'axios';
import { track, flush, initBehaviour, resetBehaviour } from './behaviour';

function makeClient() {
  return { post: vi.fn().mockResolvedValue({ data: {} }) } as unknown as AxiosInstance;
}

beforeEach(() => resetBehaviour());

describe('behaviour capture (#86)', () => {
  it('buffers then flushes a batch to /behaviour', () => {
    const client = makeClient();
    const stop = initBehaviour(client, 100000);
    track({ event_type: 'view', symbol: 'GP' });
    track({ event_type: 'sector_view', sector: 'Bank' });
    flush();
    expect(client.post).toHaveBeenCalledWith('/behaviour', {
      events: [
        { event_type: 'view', symbol: 'GP' },
        { event_type: 'sector_view', sector: 'Bank' },
      ],
    });
    stop();
  });

  it('flush is a no-op with an empty buffer', () => {
    const client = makeClient();
    const stop = initBehaviour(client, 100000);
    flush();
    expect(client.post).not.toHaveBeenCalled();
    stop();
  });
});
