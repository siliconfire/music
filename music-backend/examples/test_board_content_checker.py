from main import update_board, BoardUpdateRequest

# Fake payload dependency object expected by the endpoint
payload = {"sub": "100000"}

# 1) clean widgets
req_clean = BoardUpdateRequest(widgets=[
    {"type": "text-block", "title": "Hello", "content": "Welcome to the board"},
    {"type": "poll", "title": "Vote", "question": "Your favorite color?", "options": [{"id": "a", "label": "Red"}, {"id": "b", "label": "Blue"}]}
])

# 2) bad text-block
req_bad_text = BoardUpdateRequest(widgets=[
    {"type": "text-block", "title": "Hello", "content": "this contains badword"}
])

# 3) bad poll option
req_bad_poll = BoardUpdateRequest(widgets=[
    {"type": "poll", "title": "Vote", "question": "Best?", "options": [{"id": "a", "label": "another forbidden phrase"}]}
])


for name, req in [("clean", req_clean), ("bad_text", req_bad_text), ("bad_poll", req_bad_poll)]:
    try:
        res = update_board(req, payload)
        print(name, '-> OK')
    except Exception as e:
        print(name, '->', type(e), e)

