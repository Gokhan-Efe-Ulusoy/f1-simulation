import fastf1
fastf1.Cache.enable_cache('backend/data/raw/fastf1/cache')
for year, event in [(2023, 'Bahrain'), (2025, 'Bahrain')]:
    try:
        print(f'Trying {year} {event}')
        sess=fastf1.get_session(year, event, 'R')
        sess.load(telemetry=False)
        print(f'  success {year} {event}: {len(sess.laps)} laps')
        print(sess.laps['Compound'].unique()[:5])
    except Exception as e:
        print(f'  fail {year} {event}: {e}')
