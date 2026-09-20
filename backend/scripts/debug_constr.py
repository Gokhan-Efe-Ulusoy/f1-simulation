import json
c=json.loads(open('backend/data/calibration/models/constructor_model.json').read())
for k in ['red-bull','red-bull-racing','constructor:red-bull-racing','mercedes','mclaren','ferrari','aston-martin']:
    v=c.get(k)
    print(k, v.get('race_pace_effect') if v else 'not found')
