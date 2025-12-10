import pathlib

# Files you want to update
FILES = [
    "app.py",
    # add any other .py files here if they contain SQL, e.g.:
    # "migrate_db.py",
]

# 1) Column / field name replacements (SQLite style → Postgres snake_case)
REPLACEMENTS = {
    # users
    "UserID": "user_id",
    "Username": "username",
    "PasswordHash": "password_hash",
    "FullName": "full_name",
    "Email": "email",
    "Role": "role",
    "IsOwner": "is_owner",
    "IsAdmin": "is_admin",
    "CreatedOn": "created_on",
    "LastLogin": "last_login",

    # customers
    "CustomerID": "customer_id",
    "CustomerName": "customer_name",
    "ContactName": "contact_name",
    "ContactEmail": "contact_email",
    "ContactAddress": "contact_address",

    # rmas
    "RMAID": "rma_id",
    "CreatedByUserID": "created_by_user_id",
    "DateOpened": "date_opened",
    "DateClosed": "date_closed",
    "ClosedBy": "closed_by",
    "Status": "status",
    "ReturnType": "return_type",
    "AssignedToUserID": "assigned_to_user_id",
    "Acknowledged": "acknowledged",
    "AcknowledgedOn": "acknowledged_on",
    "AcknowledgedBy": "acknowledged_by",
    "CustomerComplaintDesc": "customer_complaint_desc",
    "InternalNotes": "internal_notes",
    "NotesLastModified": "notes_last_modified",
    "NotesModifiedBy": "notes_modified_by",
    "CreditMemoNumber": "credit_memo_number",
    "CreditAmount": "credit_amount",
    "CreditApproved": "credit_approved",
    "CreditApprovedOn": "credit_approved_on",
    "CreditApprovedBy": "credit_approved_by",
    "CreditRejected": "credit_rejected",
    "CreditRejectedOn": "credit_rejected_on",
    "CreditRejectedBy": "credit_rejected_by",
    "CreditRejectionReason": "credit_rejection_reason",
    "CreditIssuedOn": "credit_issued_on",

    # rma_lines
    "RMALineID": "rma_line_id",
    "PartNumber": "part_number",
    "ToolNumber": "tool_number",
    "ItemDescription": "item_description",
    "QtyAffected": "qty_affected",
    "POLotNumber": "po_lot_number",
    "TotalCost": "total_cost",

    # status_history
    "StatusHistID": "status_hist_id",
    "ChangedBy": "changed_by",
    "ChangedOn": "changed_on",

    # notes_history
    "NoteHistID": "note_hist_id",
    "NotesContent": "notes_content",
    "ModifiedBy": "modified_by",
    "ModifiedOn": "modified_on",

    # attachments
    "AttachmentID": "attachment_id",
    "FilePath": "file_path",
    "Filename": "filename",
    "AttachmentType": "attachment_type",
    "AddedBy": "added_by",
    "UploadedBy": "uploaded_by",
    "DateAdded": "date_added",
    "UploadedOn": "uploaded_on",

    # dispositions
    "DispositionID": "disposition_id",
    "Disposition": "disposition",
    "FailureCode": "failure_code",
    "FailureDescription": "failure_description",
    "RootCause": "root_cause",
    "CorrectiveAction": "corrective_action",
    "QtyScrap": "qty_scrap",
    "QtyRework": "qty_rework",
    "QtyReplace": "qty_replace",
    "DateDispositioned": "date_dispositioned",
    "DispositionBy": "disposition_by",

    # rma_owners
    "AssignmentID": "assignment_id",
    "IsPrimary": "is_primary",
    "AssignedOn": "assigned_on",
    "AssignedBy": "assigned_by",

    # notification_preferences
    "PreferenceID": "preference_id",
    "OwnerID": "user_id",  # renamed in Postgres schema

    # credit_history
    "CreditHistID": "credit_hist_id",
    "Action": "action",
    "Amount": "amount",
    "MemoNumber": "memo_number",
    "ActionBy": "action_by",
    "ActionOn": "action_on",
    "Comment": "comment",
}

def convert_file(path: pathlib.Path):
    original = path.read_text(encoding="utf-8")
    text = original

    # 1) Replace placeholders ? -> %s
    # This is a blunt replacement; you can refine later if needed
    if "?" in text:
        print(f"  - Replacing '?' placeholders in {path}")
        text = text.replace("?", "%s")

    # 2) Replace field names
    for old, new in REPLACEMENTS.items():
        if old in text:
            print(f"  - {path}: {old} -> {new}")
            text = text.replace(old, new)

    if text != original:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(original, encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"✅ Updated {path}, backup saved as {backup_path}")
    else:
        print(f"ℹ️ No changes needed for {path}")

def main():
    for fname in FILES:
        p = pathlib.Path(fname)
        if p.exists():
            convert_file(p)
        else:
            print(f"⚠️ File not found: {fname}")

if __name__ == "__main__":
    main()
