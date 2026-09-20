import { apiBaseUrl, ApiClientError, apiFetch } from '../app/lib/api/client';

describe('api client', () => {
  const OLD = process.env.NEXT_PUBLIC_API_URL;
  afterEach(() => {
    process.env.NEXT_PUBLIC_API_URL = OLD;
    jest.restoreAllMocks();
  });

  it('uses env base URL without trailing slash', () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://example:8000/api/v1/';
    expect(apiBaseUrl()).toBe('http://example:8000/api/v1');
  });

  it('falls back to localhost', () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    expect(apiBaseUrl()).toBe('http://localhost:8000/api/v1');
  });

  it('parses backend error envelope', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: async () => ({ error: { code: 'VALIDATION_ERROR', message: 'bad' } }),
    } as unknown as Response);
    await expect(apiFetch('/races')).rejects.toMatchObject({ code: 'VALIDATION_ERROR', httpStatus: 422 });
  });

  it('maps network failure to NETWORK_ERROR without stack leak', async () => {
    global.fetch = jest.fn().mockRejectedValue(new Error('boom'));
    const e = (await apiFetch('/races').catch((x: unknown) => x)) as ApiClientError;
    expect(e.code).toBe('NETWORK_ERROR');
    expect(e.message).toBe('boom');
  });
});
