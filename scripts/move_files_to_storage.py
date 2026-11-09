"""Move poster and return-photo bytes out of the database into Supabase Storage.

Run once after copying the data into Supabase (scripts/copy_database.py), with the app's
normal settings (DATABASE_URL, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY) in the environment
or .env:

    python scripts/move_files_to_storage.py --dry-run   # count what would move
    python scripts/move_files_to_storage.py             # move it

Each row is uploaded, then the row is pointed at the object and its bytes cleared, one row
per transaction, so the script can be stopped and re-run at any point. Afterwards run
`VACUUM FULL proposals, borrow_requests;` in the Supabase SQL editor to give the space back.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.orm import undefer  # noqa: E402

from api.database import SessionLocal  # noqa: E402
from api.models import BorrowRequest, Proposal  # noqa: E402
from api.services import storage  # noqa: E402


def move_posters(dry_run: bool) -> int:
    moved = 0
    with SessionLocal() as db:
        ids = [
            row.id
            for row in db.query(Proposal.id)
            .filter(Proposal.poster_data.is_not(None), Proposal.poster_storage_path.is_(None))
            .order_by(Proposal.id)
        ]
    print(f"Posters to move: {len(ids)}")
    for proposal_id in ids:
        with SessionLocal() as db:
            proposal = db.get(Proposal, proposal_id)
            if proposal is None or proposal.poster_data is None or proposal.poster_storage_path:
                continue
            size = len(proposal.poster_data)
            print(f"  proposal {proposal_id}: {size / 1048576:.2f} MB")
            if dry_run:
                continue
            path = storage.new_path(f"posters/{proposal_id}", proposal.poster_filename or "poster")
            storage.upload(path, proposal.poster_data, proposal.poster_content_type)
            if storage.info(path) is None:
                raise SystemExit(f"Upload of proposal {proposal_id}'s poster could not be verified; stopping.")
            proposal.poster_storage_path = path
            proposal.poster_data = None
            db.commit()
            moved += 1
    return moved


def move_return_photos(dry_run: bool) -> int:
    moved = 0
    with SessionLocal() as db:
        ids = [
            row.id
            for row in db.query(BorrowRequest.id)
            .filter(BorrowRequest.return_proof_data.is_not(None), BorrowRequest.return_proof_storage_path.is_(None))
            .order_by(BorrowRequest.id)
        ]
    print(f"Return photos to move: {len(ids)}")
    for request_id in ids:
        with SessionLocal() as db:
            request = (
                db.query(BorrowRequest).options(undefer(BorrowRequest.return_proof_data)).filter_by(id=request_id).one()
            )
            if request.return_proof_data is None or request.return_proof_storage_path:
                continue
            print(f"  borrow request {request_id}: {len(request.return_proof_data) / 1048576:.2f} MB")
            if dry_run:
                continue
            path = storage.new_path(f"borrow-proofs/{request_id}", "return.jpg")
            storage.upload(path, request.return_proof_data, request.return_proof_content_type or "image/jpeg")
            if storage.info(path) is None:
                raise SystemExit(f"Upload of borrow request {request_id}'s photo could not be verified; stopping.")
            request.return_proof_storage_path = path
            request.return_proof_data = None
            db.commit()
            moved += 1
    return moved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="list what would move and change nothing")
    args = parser.parse_args()
    posters = move_posters(args.dry_run)
    photos = move_return_photos(args.dry_run)
    if args.dry_run:
        print("Dry run only; nothing was changed.")
    else:
        print(f"Moved {posters} posters and {photos} return photos.")


if __name__ == "__main__":
    main()
