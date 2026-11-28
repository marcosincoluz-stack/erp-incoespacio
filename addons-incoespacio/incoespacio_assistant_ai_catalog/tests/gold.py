from odoo.exceptions import AccessError


def assert_never_more_than_the_screen(case, users):
    """Test de oro: para cada entrada del catálogo y cada usuario, «consultar»
    nunca devuelve un registro que ese usuario no vería en pantalla, y los
    campos que piden un grupo salen «sin permiso» a quien no lo tiene.
    """
    Question = case.env["assistant.ai.question"]
    for que, entry in Question._catalog().items():
        for user in users:
            question = Question.create({"user_id": user.id, "text": "x"})
            reply = question._run_tool(
                question._tools(), "consultar", {"que": que, "limite": 50}
            )
            rows = reply.get("result", {}).get("filas", [])
            try:
                visible = set(
                    case.env[entry["model"]].with_user(user).search(entry["domain"]).ids
                )
            except AccessError:
                visible = set()
            got = {row["id"] for row in rows}
            case.assertLessEqual(got, visible, "%s para %s" % (que, user.name))
            for label, spec in entry["fields"].items():
                if len(spec) > 2 and not user.has_group(spec[2]):
                    for row in rows:
                        case.assertEqual(
                            row.get(label, "sin permiso"), "sin permiso", (que, label)
                        )
