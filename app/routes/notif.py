from flask import Blueprint, jsonify, session, request
from app.models import Notification, db, Trip, Expense, User

notif_bp = Blueprint("notification", __name__)

@notif_bp.route("/notifications/unread_count")
def unread_count():
    if "user_id" not in session:
        return jsonify({"count": 0})
    count = Notification.unread_count(session["user_id"])
    return jsonify({"count": count})

@notif_bp.route("/notifications/list")
def list_notifications():
    if "user_id" not in session:
        return jsonify([])

    user_id = session["user_id"]
    notifs = Notification.query.filter_by(receiver_id=user_id).order_by(Notification.created_at.desc()).all()

    return jsonify([
    {
        "id": n.id,
        "message": n.message,
        "type": n.type,
        "sender": n.sender.username if n.sender else "System",
        "sender_id": n.sender_id,
        "created_at": n.created_at.strftime("%Y-%m-%d %H:%M"),
        "is_read": n.is_read,
        "trip_id": n.trip_id,
        "expense_id":n.expense_id
    }
    for n in notifs
])


@notif_bp.route("/notifications/mark_read/<int:notif_id>", methods=["POST"])
def mark_read(notif_id):
    notif = Notification.query.get_or_404(notif_id)
    notif.is_read = True
    db.session.commit()
    return jsonify({"status": "ok"})

@notif_bp.route("/notifications/respond_trip", methods=["POST"])
def respond_trip():
    data = request.get_json()

    notif_id = data.get("notif_id")
    trip_id = data.get("trip_id")
    action = data.get("action")  # "accept" or "reject"

    notif = Notification.query.get(notif_id)
    trip = Trip.query.get(trip_id)
    user = User.query.get(session["user_id"])

    if not notif or not trip or not user:
        return jsonify({"error": "Invalid request"}), 400

    original_sender = notif.sender_id

    notif.is_read = True
    db.session.delete(notif)

    if action == "accept":
        trip.participants.append(user)
        db.session.commit()

        Notification.send(
            receiver_id=original_sender,
            sender_id=user.id,
            type="trip_request_accepted",
            message=f"{user.username} accepted your trip invite.",
            trip_id=trip_id
        )

        return jsonify({"message": "Trip accepted."})

    else:
        Notification.send(
            receiver_id=original_sender,
            sender_id=user.id,
            type="trip_request_denied",
            message=f"{user.username} rejected your trip invite.",
            trip_id=trip_id
        )
        db.session.commit()
        return jsonify({"message": "Trip rejected."})

@notif_bp.route("/notifications/respond_expense", methods=["POST"])
def respond_expense():
    data = request.get_json()

    notif_id = data.get("notif_id")
    expense_id = data.get("expense_id")
    action = data.get("action")

    notif = Notification.query.get(notif_id)
    expense = Expense.query.get(expense_id)
    user = User.query.get(session["user_id"])

    if not notif or not expense or not user:
        return jsonify({"error": "Invalid request"}), 400

    original_sender = notif.sender_id

    # remove notif
    db.session.delete(notif)
    db.session.commit()

    # ACCEPT
    if action == "accept":
        if user not in expense.shared_users:
            expense.shared_users.append(user)
            db.session.commit()

        Notification.send(
            receiver_id=original_sender,
            sender_id=user.id,
            type="expense_share_accepted",
            message=f"{user.username} accepted your expense share request.",
            trip_id=expense.budget.trip_id,
            expense_id=expense.id
        )

        return jsonify({"message": "Expense accepted."})

    # DENY
    else:
        Notification.send(
            receiver_id=original_sender,
            sender_id=user.id,
            type="expense_share_denied",
            message=f"{user.username} denied your expense share request.",
            trip_id=expense.budget.trip_id,
            expense_id=expense.id
        )

        return jsonify({"message": "Expense denied."})

@notif_bp.route("/notifications/clear_all", methods=["POST"])
def clear_all():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 403

    user_id = session["user_id"]

    Notification.query.filter_by(receiver_id=user_id).delete()
    db.session.commit()

    return jsonify({"status": "cleared"})
