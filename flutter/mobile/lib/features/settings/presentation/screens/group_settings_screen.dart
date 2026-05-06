import 'package:flutter/material.dart';

class GroupSettingsScreen extends StatelessWidget {
  const GroupSettingsScreen({
    required this.groupId,
    super.key,
  });

  final String groupId;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: <Widget>[
        Text(
          'Ajustes del grupo',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 8),
        Text(
          'Las acciones sensibles de este tab dependen del rol admin en group_members.',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const <Widget>[
                Text('Código del grupo: DEMO01'),
                SizedBox(height: 12),
                Text('Acciones futuras'),
                Text('Renombrar grupo'),
                Text('Ver miembros'),
                Text('Expulsar miembro'),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
