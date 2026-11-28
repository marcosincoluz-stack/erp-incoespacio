def migrate(cr, version):
    # Una vez: las obras sin responsable quedan con quien las creó.
    cr.execute(
        """
        UPDATE project_project
           SET user_id = create_uid
         WHERE user_id IS NULL
           AND create_uid IS NOT NULL
        """
    )
