import 'package:flutter/material.dart';

class PlayersScreen extends StatelessWidget {
  const PlayersScreen({
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
          'Jugadores',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 8),
        Text(
          'Los jugadores son entidades del grupo, no usuarios de la app.',
          style: Theme.of(context).textTheme.bodyLarge,
        ),
        const SizedBox(height: 20),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  'Pendientes del módulo',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 12),
                const Text('Alta simple por apodo'),
                const Text('Baja lógica conservando historial'),
                const Text('Mini-stats por jugador'),
                const Text('Vinculación opcional con usuario en versiones futuras'),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
