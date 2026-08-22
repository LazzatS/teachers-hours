from google.cloud import firestore

db = firestore.Client(database='teachers-hours')

for t in db.collection('topics').stream():
    print(t.id, t.to_dict())
    for s in t.reference.collection('skills').stream():
        print('   ', s.to_dict())
