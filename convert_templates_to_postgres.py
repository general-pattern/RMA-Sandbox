import pathlib
import re

# Directory that holds your templates
TEMPLATE_DIR = pathlib.Path("templates")

# Mapping from old TitleCase field names -> new snake_case DB columns
FIELD_MAP = {
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
    "CustomerID": "customer_id",
    "CreatedByUserID": "created_by_user_id",
    "CreatedByName": "created_by_name",  # if you alias this in queries
    "DateOpened": "date_opened",
    "DateClosed": "date_closed",
    "ClosedBy": "closed_by",
    "Status": "status",
    "ReturnType": "return_type",
    "InternalOwnerID": "internal_owner_id",  # if still used anywhere
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

    # status history
    "StatusHistID": "status_hist_id",
    "ChangedOn": "changed_on",
    "ChangedBy": "changed_by",
    "Comment": "comment",

    # notes history
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

    # rma_owners & notifications & credit_history if referenced in templates
    "AssignmentID": "assignment_id",
    "IsPrimary": "is_primary",
    "AssignedOn": "assigned_on",
    "AssignedBy": "assigned_by",
    "PreferenceID": "preference_id",
    "OwnerID": "user_id",
    "CreditHistID": "credit_hist_id",
    "Action": "action",
    "Amount": "amount",
    "MemoNumber": "memo_number",
    "ActionBy": "action_by",
    "ActionOn": "action_on",
}

def convert_file(path: pathlib.Path):
    original = path.read_text(encoding="utf-8")
    text = original

    for old, new in FIELD_MAP.items():
        # Replace dictionary-style access: obj['OldName'] -> obj['new_name']
        pattern_bracket_single = r"\['" + re.escape(old) + r"'\]"
        pattern_bracket_double = r"\[\"" + re.escape(old) + r"\"\]"

        repl_single = "['" + new + "']"
        repl_double = '["' + new + '"]'

        new_text = re.sub(pattern_bracket_single, repl_single, text)
        new_text = re.sub(pattern_bracket_double, repl_double, new_text)

        # Replace dot access: obj.OldName -> obj.new_name
        # Only when it's clearly an attribute: .OldName followed by non-word or end
        pattern_dot = r"\." + re.escape(old) + r"\b"
        repl_dot = "." + new

        new_text = re.sub(pattern_dot, repl_dot, new_text)

        if new_text != text:
            print(f"  - {path.name}: {old} -> {new}")
            text = new_text

    if text != original:
        backup_path = path.with_suffix(path.suffix + ".bak")
        backup_path.write_text(original, encoding="utf-8")
        path.write_text(text, encoding="utf-8")
        print(f"✅ Updated {path}, backup saved as {backup_path}")
    else:
        print(f"ℹ️ No changes needed for {path}")

def main():
    if not TEMPLATE_DIR.exists():
        print(f"❌ Templates directory not found: {TEMPLATE_DIR}")
        return

    for path in TEMPLATE_DIR.rglob("*.html"):
        print(f"Processing {path} ...")
        convert_file(path)

if __name__ == "__main__":
    main()
